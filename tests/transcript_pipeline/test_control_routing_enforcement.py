"""
H01B-4 Control Routing Enforcement Tests

Ensures routing is gate-evidence-gated. TLC does not own control authority —
it verifies gate evidence produced by an upstream evaluator.

Scenarios:
1.  valid artifact, no gate_evidence        → FAIL (MISSING_GATE_EVIDENCE)
2.  valid artifact, gate_status=failed_gate → FAIL (GATE_EVIDENCE_NOT_ROUTABLE)
3.  valid artifact, gate_status=passed_gate → PASS (accepted_for_route)
4.  tampered artifact after eval            → FAIL (hash mismatch on store registration)
5.  missing eval_summary_id                 → FAIL (MISSING_EVAL_SUMMARY_ID)
6.  missing gate_status field               → FAIL (MISSING_GATE_STATUS)
7.  gate_status=missing_gate                → FAIL (GATE_EVIDENCE_NOT_ROUTABLE)
8.  gate_status=conditional_gate, not opted in  → FAIL
9.  gate_status=conditional_gate, opted in      → PASS
10. terminal artifact type after passed gate    → FAIL (TERMINAL_ARTIFACT_TYPE)
11. target_artifact_id mismatch             → FAIL (ARTIFACT_ID_MISMATCH)
12. unknown gate_status value               → FAIL (UNKNOWN_GATE_STATUS)
"""
from __future__ import annotations

from typing import Any, Dict

import pytest

from spectrum_systems.modules.orchestration.tlc_router import (
    ArtifactRoutingError,
    route_with_gate_evidence,
)
from spectrum_systems.modules.runtime.artifact_store import (
    ArtifactStore,
    ArtifactStoreError,
)
from tests.transcript_pipeline.conftest import _make_transcript_artifact


def _pass_gate(summary_id: str = "EVAL-001") -> Dict[str, Any]:
    return {"eval_summary_id": summary_id, "gate_status": "passed_gate"}


def _gate(gate_status: str, summary_id: str = "EVAL-001") -> Dict[str, Any]:
    return {"eval_summary_id": summary_id, "gate_status": gate_status}


class TestRouteWithGateEvidence:
    """H01B-2/H01B-4: route_with_gate_evidence enforces gate evidence presence."""

    def test_passed_gate_routes_correctly(self) -> None:
        artifact = _make_transcript_artifact()
        next_type = route_with_gate_evidence(artifact, _pass_gate())
        assert next_type == "context_bundle"

    def test_no_gate_evidence_raises(self) -> None:
        artifact = _make_transcript_artifact()
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_with_gate_evidence(artifact, None)  # type: ignore[arg-type]
        assert "MISSING_GATE_EVIDENCE" in exc_info.value.reason_codes

    def test_non_dict_gate_evidence_raises(self) -> None:
        artifact = _make_transcript_artifact()
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_with_gate_evidence(artifact, "passed_gate")  # type: ignore[arg-type]
        assert "MISSING_GATE_EVIDENCE" in exc_info.value.reason_codes

    def test_failed_gate_is_rejected_for_route(self) -> None:
        artifact = _make_transcript_artifact()
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_with_gate_evidence(artifact, _gate("failed_gate"))
        assert "GATE_EVIDENCE_NOT_ROUTABLE" in exc_info.value.reason_codes

    def test_missing_gate_is_rejected_for_route(self) -> None:
        artifact = _make_transcript_artifact()
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_with_gate_evidence(artifact, _gate("missing_gate"))
        assert "GATE_EVIDENCE_NOT_ROUTABLE" in exc_info.value.reason_codes

    def test_conditional_gate_rejected_by_default(self) -> None:
        artifact = _make_transcript_artifact()
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_with_gate_evidence(artifact, _gate("conditional_gate"))
        assert "GATE_EVIDENCE_CONDITIONAL_ROUTING_NOT_ENABLED" in exc_info.value.reason_codes

    def test_conditional_gate_accepted_when_opted_in(self) -> None:
        artifact = _make_transcript_artifact()
        next_type = route_with_gate_evidence(
            artifact, _gate("conditional_gate"), conditional_route_allowed=True
        )
        assert next_type == "context_bundle"

    def test_missing_eval_summary_id_raises(self) -> None:
        artifact = _make_transcript_artifact()
        cd = {"gate_status": "passed_gate"}
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_with_gate_evidence(artifact, cd)
        assert "MISSING_EVAL_SUMMARY_ID" in exc_info.value.reason_codes

    def test_missing_gate_status_field_raises(self) -> None:
        artifact = _make_transcript_artifact()
        cd = {"eval_summary_id": "EVAL-001"}
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_with_gate_evidence(artifact, cd)
        assert "MISSING_GATE_STATUS" in exc_info.value.reason_codes

    def test_unknown_gate_status_raises(self) -> None:
        artifact = _make_transcript_artifact()
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_with_gate_evidence(artifact, _gate("maybe_gate"))
        assert "UNKNOWN_GATE_STATUS" in exc_info.value.reason_codes

    def test_terminal_artifact_type_rejected_after_passed_gate(self) -> None:
        artifact = {"artifact_type": "release_artifact"}
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_with_gate_evidence(artifact, _pass_gate())
        assert "TERMINAL_ARTIFACT_TYPE" in exc_info.value.reason_codes

    def test_target_artifact_id_mismatch_raises(self) -> None:
        artifact = _make_transcript_artifact()
        gate_ev = {
            "eval_summary_id": "EVAL-001",
            "gate_status": "passed_gate",
            "target_artifact_id": "TXA-WRONG-ID",
        }
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_with_gate_evidence(artifact, gate_ev)
        assert "ARTIFACT_ID_MISMATCH" in exc_info.value.reason_codes

    def test_target_artifact_id_match_passes(self) -> None:
        artifact = _make_transcript_artifact()
        gate_ev = {
            "eval_summary_id": "EVAL-001",
            "gate_status": "passed_gate",
            "target_artifact_id": artifact["artifact_id"],
        }
        next_type = route_with_gate_evidence(artifact, gate_ev)
        assert next_type == "context_bundle"


class TestTamperedArtifactDetection:
    """H01B-4 scenario 4: tampered artifact rejected by store hash check."""

    def test_tampered_artifact_rejected_by_store(self) -> None:
        store = ArtifactStore()
        artifact = _make_transcript_artifact()
        artifact["raw_text"] = "TAMPERED CONTENT"
        with pytest.raises(ArtifactStoreError) as exc_info:
            store.register_artifact(artifact)
        assert exc_info.value.reason_code == "CONTENT_HASH_MISMATCH"

    def test_original_artifact_accepted_after_passed_gate(self) -> None:
        store = ArtifactStore()
        artifact = _make_transcript_artifact()
        artifact_id = store.register_artifact(artifact)
        assert artifact_id == artifact["artifact_id"]


class TestGateEvidenceMissingBlock:
    """H01B-4 scenario 5: missing eval_summary_id blocks routing."""

    def test_routing_rejected_without_eval_summary_id(self) -> None:
        artifact = _make_transcript_artifact()
        gate_ev = {"gate_status": "passed_gate"}
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_with_gate_evidence(artifact, gate_ev)
        assert "MISSING_EVAL_SUMMARY_ID" in exc_info.value.reason_codes

    def test_routing_accepted_for_route_with_full_passed_gate(self) -> None:
        artifact = _make_transcript_artifact()
        result = route_with_gate_evidence(artifact, _pass_gate())
        assert result == "context_bundle"
