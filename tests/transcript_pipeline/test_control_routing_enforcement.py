"""
H01B-4 Control Routing Enforcement Tests

Ensures routing is impossible without a valid 'allow' control decision.

Scenarios:
1. valid artifact, no control_decision → FAIL (MISSING_CONTROL_DECISION)
2. valid artifact, control_decision=block → FAIL (CONTROL_DECISION_BLOCK)
3. valid artifact, control_decision=allow → PASS
4. tampered artifact after eval → FAIL (hash mismatch on store registration)
5. missing eval_summary → FAIL (MISSING_EVAL_SUMMARY)
6. missing evaluation_control_decision field → FAIL
7. control_decision=freeze → FAIL
8. control_decision=warn, warn_allowed=False → FAIL
9. control_decision=warn, warn_allowed=True → PASS
10. control_decision=allow but artifact_type is terminal → FAIL (TERMINAL_ARTIFACT_TYPE)
"""
from __future__ import annotations

import copy
from typing import Any, Dict

import pytest

from spectrum_systems.modules.orchestration.tlc_router import (
    ArtifactRoutingError,
    route_with_control_check,
)
from spectrum_systems.modules.runtime.artifact_store import (
    ArtifactStore,
    ArtifactStoreError,
    compute_content_hash,
)
from tests.transcript_pipeline.conftest import _make_transcript_artifact


def _allow_decision() -> Dict[str, Any]:
    return {
        "eval_summary": "All eval gates passed.",
        "evaluation_control_decision": "allow",
    }


def _decision(decision: str, summary: str = "eval complete") -> Dict[str, Any]:
    return {
        "eval_summary": summary,
        "evaluation_control_decision": decision,
    }


class TestRouteWithControlCheck:
    """H01B-2/H01B-4: route_with_control_check enforces control decision."""

    def test_allow_decision_routes_correctly(self) -> None:
        artifact = _make_transcript_artifact()
        next_type = route_with_control_check(artifact, _allow_decision())
        assert next_type == "context_bundle"

    def test_no_control_decision_raises(self) -> None:
        artifact = _make_transcript_artifact()
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_with_control_check(artifact, None)  # type: ignore[arg-type]
        assert "MISSING_CONTROL_DECISION" in exc_info.value.reason_codes

    def test_non_dict_control_decision_raises(self) -> None:
        artifact = _make_transcript_artifact()
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_with_control_check(artifact, "allow")  # type: ignore[arg-type]
        assert "MISSING_CONTROL_DECISION" in exc_info.value.reason_codes

    def test_block_decision_raises(self) -> None:
        artifact = _make_transcript_artifact()
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_with_control_check(artifact, _decision("block"))
        assert "CONTROL_DECISION_BLOCK" in exc_info.value.reason_codes

    def test_freeze_decision_raises(self) -> None:
        artifact = _make_transcript_artifact()
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_with_control_check(artifact, _decision("freeze"))
        assert "CONTROL_DECISION_FREEZE" in exc_info.value.reason_codes

    def test_warn_decision_rejected_by_default(self) -> None:
        artifact = _make_transcript_artifact()
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_with_control_check(artifact, _decision("warn"))
        assert "CONTROL_DECISION_WARN_NOT_ALLOWED" in exc_info.value.reason_codes

    def test_warn_decision_allowed_when_opted_in(self) -> None:
        artifact = _make_transcript_artifact()
        next_type = route_with_control_check(artifact, _decision("warn"), warn_allowed=True)
        assert next_type == "context_bundle"

    def test_missing_eval_summary_raises(self) -> None:
        artifact = _make_transcript_artifact()
        cd = {"evaluation_control_decision": "allow"}
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_with_control_check(artifact, cd)
        assert "MISSING_EVAL_SUMMARY" in exc_info.value.reason_codes

    def test_missing_evaluation_control_decision_field_raises(self) -> None:
        artifact = _make_transcript_artifact()
        cd = {"eval_summary": "complete"}
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_with_control_check(artifact, cd)
        assert "MISSING_EVALUATION_CONTROL_DECISION" in exc_info.value.reason_codes

    def test_unknown_decision_value_raises(self) -> None:
        artifact = _make_transcript_artifact()
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_with_control_check(artifact, _decision("maybe"))
        assert "UNKNOWN_CONTROL_DECISION" in exc_info.value.reason_codes

    def test_terminal_artifact_type_still_raises_after_allow(self) -> None:
        artifact = {"artifact_type": "release_artifact"}
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_with_control_check(artifact, _allow_decision())
        assert "TERMINAL_ARTIFACT_TYPE" in exc_info.value.reason_codes


class TestTamperedArtifactDetection:
    """H01B-4 scenario 4: tampered artifact rejected by store hash check."""

    def test_tampered_artifact_rejected_by_store(self) -> None:
        store = ArtifactStore()
        artifact = _make_transcript_artifact()

        # Simulate tampering after eval: mutate content but keep old hash
        original_hash = artifact["content_hash"]
        artifact["raw_text"] = "TAMPERED CONTENT"

        # Store must reject: computed hash won't match stored hash
        with pytest.raises(ArtifactStoreError) as exc_info:
            store.register_artifact(artifact)
        assert exc_info.value.reason_code == "CONTENT_HASH_MISMATCH"

    def test_original_artifact_accepted_after_allow(self) -> None:
        store = ArtifactStore()
        artifact = _make_transcript_artifact()
        artifact_id = store.register_artifact(artifact)
        assert artifact_id == artifact["artifact_id"]


class TestMissingEvalSummaryBlock:
    """H01B-4 scenario 5: missing eval_summary blocks routing."""

    def test_routing_blocked_without_eval_summary(self) -> None:
        artifact = _make_transcript_artifact()
        cd_no_eval = {"evaluation_control_decision": "allow"}
        with pytest.raises(ArtifactRoutingError) as exc_info:
            route_with_control_check(artifact, cd_no_eval)
        assert "MISSING_EVAL_SUMMARY" in exc_info.value.reason_codes

    def test_routing_permitted_with_full_allow_decision(self) -> None:
        artifact = _make_transcript_artifact()
        result = route_with_control_check(artifact, _allow_decision())
        assert result == "context_bundle"
