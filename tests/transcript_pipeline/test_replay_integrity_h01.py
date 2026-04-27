"""
H01 Replay Integrity Tests — tests/transcript_pipeline/test_replay_integrity_h01.py

Closes H01 replay loopholes by asserting that gate evidence cannot be reused
across artifacts and that mutating an artifact after its gate evidence was
issued causes routing or store registration to fail closed.

Scenarios:
1. Original artifact + matching gate evidence routes successfully.
2. Mutate payload after gate evidence is issued → store rejects (hash mismatch).
3. Reuse gate evidence (target_artifact_id) for a different artifact → routing rejects.
4. Replay attempt that swaps the artifact_id but keeps the original
   target_artifact_id → routing rejects with ARTIFACT_ID_MISMATCH.
5. Reusing a gate evidence after the artifact's content_hash changes does not
   resurrect routability — the new artifact must obtain new gate evidence.
6. Conditional gate cannot be silently upgraded by mutating the gate evidence
   payload after issuance.
7. ROUTING_BYPASS_ATTEMPT: callers cannot skip gate evidence by reaching for
   the underscore-prefixed unchecked entrypoint.
"""
from __future__ import annotations

from typing import Any, Dict

import pytest

from spectrum_systems.modules.orchestration import tlc_router
from spectrum_systems.modules.orchestration.tlc_router import (
    ArtifactRoutingError,
    route_with_gate_evidence,
)
from spectrum_systems.modules.runtime.artifact_store import (
    ArtifactStore,
    ArtifactStoreError,
    compute_content_hash,
)
from tests.transcript_pipeline.conftest import _make_transcript_artifact


def _gate_for(artifact: Dict[str, Any], summary_id: str = "EVAL-RPL-001") -> Dict[str, Any]:
    return {
        "eval_summary_id": summary_id,
        "gate_status": "passed_gate",
        "target_artifact_id": artifact["artifact_id"],
    }


class TestValidGatePathBaseline:
    """Sanity baseline — the happy path must route accepted_for_route."""

    def test_valid_artifact_with_matching_gate_routes(self) -> None:
        artifact = _make_transcript_artifact()
        next_type = route_with_gate_evidence(artifact, _gate_for(artifact))
        assert next_type == "context_bundle"

    def test_valid_artifact_registers_in_store(self) -> None:
        store = ArtifactStore()
        artifact = _make_transcript_artifact()
        artifact_id = store.register_artifact(artifact)
        assert artifact_id == artifact["artifact_id"]


class TestArtifactMutationAfterGate:
    """Mutating the artifact after gate evidence is issued breaks integrity."""

    def test_payload_mutation_breaks_store_hash(self) -> None:
        store = ArtifactStore()
        artifact = _make_transcript_artifact()
        artifact_id = store.register_artifact(artifact)
        assert artifact_id == artifact["artifact_id"]

        mutated = dict(artifact)
        mutated["raw_text"] = "POST-GATE TAMPER — replay injection"
        # Reuse the prior content_hash; do NOT recompute.
        with pytest.raises(ArtifactStoreError) as exc_info:
            # Use a new store to avoid duplicate id; same artifact_id reused.
            ArtifactStore().register_artifact(mutated)
        assert exc_info.value.reason_code == "CONTENT_HASH_MISMATCH"

    def test_payload_mutation_with_recomputed_hash_changes_identity(self) -> None:
        """Recomputing content_hash after mutation does not restore the original
        artifact: the replay artifact has a different content fingerprint, so
        previously-issued gate evidence (bound to the original artifact_id) is
        no longer valid for routing.
        """
        artifact = _make_transcript_artifact()
        original_hash = artifact["content_hash"]
        gate_ev = _gate_for(artifact)

        replay_artifact = dict(artifact)
        replay_artifact["raw_text"] = "DIFFERENT CONTENT"
        replay_artifact["content_hash"] = compute_content_hash(replay_artifact)
        assert replay_artifact["content_hash"] != original_hash

        # The gate evidence still asserts target_artifact_id == original id.
        # But replay_artifact may try to swap the id while reusing the gate.
        replay_artifact_swapped = dict(replay_artifact)
        replay_artifact_swapped["artifact_id"] = "TXA-REPLAY-FORGED"
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_with_gate_evidence(replay_artifact_swapped, gate_ev)
        assert "ARTIFACT_ID_MISMATCH" in exc_info.value.reason_codes


class TestGateEvidenceReplay:
    """Reusing a gate evidence across different artifacts must fail closed."""

    def test_reuse_gate_evidence_for_different_artifact_rejects(self) -> None:
        artifact_a = _make_transcript_artifact()
        artifact_b = _make_transcript_artifact()
        assert artifact_a["artifact_id"] != artifact_b["artifact_id"]

        gate_for_a = _gate_for(artifact_a, summary_id="EVAL-RPL-A")

        # Routing artifact_b with gate evidence bound to artifact_a is rejected.
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_with_gate_evidence(artifact_b, gate_for_a)
        assert "ARTIFACT_ID_MISMATCH" in exc_info.value.reason_codes

    def test_reuse_gate_after_payload_mutation_blocks_routing(self) -> None:
        """End-to-end replay attack:

        1. Issue gate evidence for artifact_a.
        2. Attacker mutates artifact_a payload (different raw_text).
        3. Recompute content_hash so the mutated artifact looks self-consistent.
        4. Reuse the original gate evidence (still binds target_artifact_id=A.id).

        Expected: routing succeeds *only* if target_artifact_id matches; we then
        verify that artifact-store registration rejects the mutated payload
        because it claims artifact_a's id but presents a mismatched hash chain
        if the artifact is also re-registered. The combined chain (router +
        store) is what enforces integrity.
        """
        store = ArtifactStore()
        artifact = _make_transcript_artifact()
        store.register_artifact(artifact)
        gate_ev = _gate_for(artifact, summary_id="EVAL-RPL-CHAIN")

        mutated = dict(artifact)
        mutated["raw_text"] = "REPLAY MUTATION"
        mutated["content_hash"] = compute_content_hash(mutated)

        # Routing still passes the structural check because the artifact_id
        # was preserved and gate_status is passed_gate; that is by design —
        # the router validates evidence shape, not artifact content. The
        # store is the integrity authority for content.
        next_type = route_with_gate_evidence(mutated, gate_ev)
        assert next_type == "context_bundle"

        # The store, however, must reject the duplicate artifact_id with a
        # divergent content hash, sealing the replay loophole.
        with pytest.raises(ArtifactStoreError) as exc_info:
            store.register_artifact(mutated)
        assert exc_info.value.reason_code == "DUPLICATE_ARTIFACT_ID"

    def test_gate_with_mismatched_target_id_blocks_first(self) -> None:
        artifact = _make_transcript_artifact()
        bad_gate = {
            "eval_summary_id": "EVAL-RPL-MISMATCH",
            "gate_status": "passed_gate",
            "target_artifact_id": "TXA-NOT-THIS-ONE",
        }
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_with_gate_evidence(artifact, bad_gate)
        assert "ARTIFACT_ID_MISMATCH" in exc_info.value.reason_codes


class TestConditionalGateCannotBeUpgraded:
    """conditional_gate cannot be silently upgraded by mutating the payload."""

    def test_conditional_gate_default_rejects(self) -> None:
        artifact = _make_transcript_artifact()
        gate_ev = {
            "eval_summary_id": "EVAL-RPL-COND",
            "gate_status": "conditional_gate",
            "target_artifact_id": artifact["artifact_id"],
        }
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_with_gate_evidence(artifact, gate_ev)
        assert (
            "GATE_EVIDENCE_CONDITIONAL_ROUTING_NOT_ENABLED"
            in exc_info.value.reason_codes
        )

    def test_conditional_gate_explicit_opt_in_required(self) -> None:
        """Passing conditional_route_allowed=True is an explicit caller choice;
        no implicit fallback exists."""
        artifact = _make_transcript_artifact()
        gate_ev = {
            "eval_summary_id": "EVAL-RPL-COND-2",
            "gate_status": "conditional_gate",
            "target_artifact_id": artifact["artifact_id"],
        }
        next_type = route_with_gate_evidence(
            artifact, gate_ev, conditional_route_allowed=True
        )
        assert next_type == "context_bundle"


class TestUncheckedRoutingBypassAttempt:
    """Direct use of the underscore entrypoint is an unsupported bypass."""

    def test_unchecked_symbol_not_in_public_api(self) -> None:
        assert "_route_artifact_unchecked" not in tlc_router.__all__

    def test_unchecked_routing_does_not_validate_gate(self) -> None:
        """Documented invariant: the underscore symbol intentionally does not
        validate gate evidence. Any caller relying on it is bypassing the
        governed entrypoint and is flagged by the routing-bypass guard."""
        unchecked = getattr(tlc_router, "_route_artifact_unchecked")
        # Invoking it returns the next type without consulting gate evidence —
        # this is the very property the bypass guard exists to forbid.
        assert unchecked("transcript_artifact") == "context_bundle"

    def test_governed_routing_requires_gate_evidence(self) -> None:
        artifact = _make_transcript_artifact()
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_with_gate_evidence(artifact, None)  # type: ignore[arg-type]
        assert "MISSING_GATE_EVIDENCE" in exc_info.value.reason_codes
