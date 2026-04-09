from __future__ import annotations

import copy

import pytest

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.review_promotion_gate import (
    ReviewPromotionGateError,
    emit_review_promotion_gate,
)


def _safe_review_pair() -> tuple[dict, dict]:
    review_result = copy.deepcopy(load_example("review_result_artifact"))
    merge_readiness = copy.deepcopy(load_example("review_merge_readiness_artifact"))

    review_result["review_id"] = "rqx-02-review-002"
    review_result["verdict"] = "safe_to_merge"
    review_result["required_follow_up"] = []
    review_result["findings"] = [
        {
            "finding_id": "F-1",
            "title": "No blocking signals detected in bounded scope",
            "severity": "low",
            "evidence": ["artifacts/pqx_runs/run-001/output.json"],
            "why_it_matters": "Bounded review records explicit evidence for traceability.",
        }
    ]

    merge_readiness["review_id"] = "rqx-02-review-002"
    merge_readiness["review_result_ref"] = "review_result_artifact:rqx-02-review-002"
    merge_readiness["verdict"] = "safe_to_merge"
    merge_readiness["merge_ready"] = True
    merge_readiness["required_follow_up"] = []
    return review_result, merge_readiness


def test_review_promotion_gate_contract_example_validates() -> None:
    validate_artifact(load_example("review_promotion_gate_artifact"), "review_promotion_gate_artifact")


def test_safe_to_merge_without_unresolved_state_allows_promotion_gate(tmp_path) -> None:
    review_result, merge_readiness = _safe_review_pair()

    result = emit_review_promotion_gate(
        review_result_artifact=review_result,
        review_merge_readiness_artifact=merge_readiness,
        closure_decision_artifact=copy.deepcopy(load_example("closure_decision_artifact")),
        output_dir=tmp_path,
    )

    gate = result["review_promotion_gate_artifact"]
    assert gate["signal_status"] == "clean"
    assert gate["gate_reason_code"] == "safe_to_merge"
    assert gate["required_manual_action"] is False
    validate_artifact(gate, "review_promotion_gate_artifact")


def test_missing_required_review_artifacts_fails_closed(tmp_path) -> None:
    result = emit_review_promotion_gate(
        review_result_artifact=None,
        review_merge_readiness_artifact=None,
        closure_decision_artifact=None,
        output_dir=tmp_path,
    )

    gate = result["review_promotion_gate_artifact"]
    assert gate["signal_status"] == "invalid"
    assert gate["gate_reason_code"] == "missing_required_review_artifact"



def test_unresolved_handoff_without_disposition_holds_manual_resolution(tmp_path) -> None:
    review_result, merge_readiness = _safe_review_pair()
    handoff = copy.deepcopy(load_example("review_operator_handoff_artifact"))
    handoff["review_id"] = review_result["review_id"]
    handoff["source_review_result_ref"] = f"review_result_artifact:{review_result['review_id']}"

    result = emit_review_promotion_gate(
        review_result_artifact=review_result,
        review_merge_readiness_artifact=merge_readiness,
        closure_decision_artifact=copy.deepcopy(load_example("closure_decision_artifact")),
        review_operator_handoff_artifact=handoff,
        output_dir=tmp_path,
    )

    gate = result["review_promotion_gate_artifact"]
    assert gate["signal_status"] == "manual_review_required"
    assert gate["gate_reason_code"] == "handoff_pending"


@pytest.mark.parametrize(
    ("disposition", "reason_code", "expected_signal", "expected_gate_reason"),
    [
        ("manual_review_required", "missing_prerequisite", "manual_review_required", "disposition_requires_manual_review"),
        ("escalate_to_owner", "not_safe_to_merge", "manual_review_required", "unresolved_not_safe_to_merge"),
        ("hold_pending_input", "execution_failed", "manual_review_required", "disposition_requires_manual_review"),
        ("schedule_follow_on_cycle", "unresolved_fix_required", "manual_review_required", "unresolved_fix_required"),
    ],
)
def test_disposition_outcomes_do_not_allow_promotion(
    tmp_path,
    disposition: str,
    reason_code: str,
    expected_signal: str,
    expected_gate_reason: str,
) -> None:
    review_result, merge_readiness = _safe_review_pair()
    handoff = copy.deepcopy(load_example("review_operator_handoff_artifact"))
    handoff["review_id"] = review_result["review_id"]
    handoff["source_review_result_ref"] = f"review_result_artifact:{review_result['review_id']}"

    disposition_artifact = copy.deepcopy(load_example("review_handoff_disposition_artifact"))
    disposition_artifact["source_review_id"] = review_result["review_id"]
    disposition_artifact["source_handoff_ref"] = f"review_operator_handoff_artifact:{handoff['handoff_id']}"
    disposition_artifact["disposition"] = disposition
    disposition_artifact["reason_code"] = reason_code

    result = emit_review_promotion_gate(
        review_result_artifact=review_result,
        review_merge_readiness_artifact=merge_readiness,
        closure_decision_artifact=copy.deepcopy(load_example("closure_decision_artifact")),
        review_operator_handoff_artifact=handoff,
        review_handoff_disposition_artifact=disposition_artifact,
        output_dir=tmp_path,
    )

    gate = result["review_promotion_gate_artifact"]
    assert gate["signal_status"] == expected_signal
    assert gate["gate_reason_code"] == expected_gate_reason


def test_ambiguous_review_state_is_blocked(tmp_path) -> None:
    review_result, merge_readiness = _safe_review_pair()
    merge_readiness["merge_ready"] = False

    result = emit_review_promotion_gate(
        review_result_artifact=review_result,
        review_merge_readiness_artifact=merge_readiness,
        closure_decision_artifact=copy.deepcopy(load_example("closure_decision_artifact")),
        output_dir=tmp_path,
    )

    gate = result["review_promotion_gate_artifact"]
    assert gate["signal_status"] == "invalid"
    assert gate["gate_reason_code"] == "ambiguous_review_state"


def test_promotion_gate_emits_once_per_review_state(tmp_path) -> None:
    review_result, merge_readiness = _safe_review_pair()

    emit_review_promotion_gate(
        review_result_artifact=review_result,
        review_merge_readiness_artifact=merge_readiness,
        closure_decision_artifact=copy.deepcopy(load_example("closure_decision_artifact")),
        output_dir=tmp_path,
    )
    with pytest.raises(ReviewPromotionGateError, match="already exists"):
        emit_review_promotion_gate(
            review_result_artifact=review_result,
            review_merge_readiness_artifact=merge_readiness,
            closure_decision_artifact=copy.deepcopy(load_example("closure_decision_artifact")),
            output_dir=tmp_path,
        )


def test_gate_artifact_does_not_trigger_merge_or_closure_authority(tmp_path) -> None:
    review_result, merge_readiness = _safe_review_pair()
    result = emit_review_promotion_gate(
        review_result_artifact=review_result,
        review_merge_readiness_artifact=merge_readiness,
        closure_decision_artifact=copy.deepcopy(load_example("closure_decision_artifact")),
        output_dir=tmp_path,
    )
    gate = result["review_promotion_gate_artifact"]

    assert "merge_action" not in gate
    assert "promotion_action" not in gate
    assert "closure_decision" not in gate
    assert gate["provenance"]["automatic_merge_triggered"] is False
    assert gate["provenance"]["automatic_promotion_triggered"] is False
    assert gate["provenance"]["closure_authority_transferred"] is False
