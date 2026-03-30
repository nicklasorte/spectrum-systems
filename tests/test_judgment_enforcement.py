from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.contracts import load_example  # noqa: E402
from spectrum_systems.modules.runtime.control_loop import run_judgment_learning_control_loop  # noqa: E402
from spectrum_systems.modules.runtime.judgment_enforcement import (  # noqa: E402
    build_judgment_progression_reinstatement_record,
    build_judgment_remediation_closure_record,
    evaluate_judgment_enforcement_traceability,
    transition_judgment_remediation_status,
)


def _inputs() -> dict[str, Any]:
    drift = copy.deepcopy(load_example("judgment_drift_signal"))
    drift["group_signals"][0]["deltas"] = {
        "approval_rate_delta": 0.01,
        "block_rate_delta": 0.01,
        "error_rate_delta": 0.01,
        "calibration_ece_delta": 0.01,
    }
    drift["group_signals"][0]["drift_detected"] = False
    calibration = copy.deepcopy(load_example("judgment_calibration_result"))
    calibration["group_metrics"][0]["expected_calibration_error"] = 0.02
    return {
        "judgment_eval_result": copy.deepcopy(load_example("judgment_eval_result")),
        "judgment_calibration_result": calibration,
        "judgment_drift_signal": drift,
        "judgment_error_budget_status": copy.deepcopy(load_example("judgment_error_budget_status")),
        "judgment_policy": copy.deepcopy(load_example("judgment_policy")),
        "trace_context": {"trace_id": "trace-001", "replay_run_id": "run-001"},
        "created_at": "2026-03-30T00:20:00Z",
    }


def _close_and_reinstate(
    result: dict[str, Any],
    *,
    reinstatement_type: str,
    next_state: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    remediation = result["judgment_operator_remediation_record"]
    remediation = transition_judgment_remediation_status(
        remediation,
        target_status="in_progress",
        changed_at="2026-03-30T01:00:00Z",
        changed_by_role="operator",
        rationale="operator started remediation",
    )
    remediation = transition_judgment_remediation_status(
        remediation,
        target_status="evidence_submitted",
        changed_at="2026-03-30T01:05:00Z",
        changed_by_role="operator",
        rationale="required evidence uploaded",
    )
    remediation = transition_judgment_remediation_status(
        remediation,
        target_status="pending_review",
        changed_at="2026-03-30T01:08:00Z",
        changed_by_role="operator",
        rationale="submitted for governance review",
    )
    remediation = transition_judgment_remediation_status(
        remediation,
        target_status="approved_for_closure",
        changed_at="2026-03-30T01:12:00Z",
        changed_by_role="reviewer",
        rationale="review passed",
    )

    closure = build_judgment_remediation_closure_record(
        remediation_record=remediation,
        escalation_record=result["judgment_control_escalation_record"],
        action_record=result["judgment_enforcement_action_record"],
        outcome_record=result["judgment_enforcement_outcome_record"],
        evidence_artifact_refs=remediation["required_evidence_artifacts"],
        threshold_checks={
            "source_condition_addressed": True,
            "eval_thresholds_met": True,
            "drift_threshold_met": True,
        },
        policy_version="1.0.0",
        created_at="2026-03-30T01:14:00Z",
        approval_status="approved",
        approval_actor_ref="operator_release_approval_record:release-001",
        rationale="Replay-safe checks prove remediation sufficiency.",
    )

    remediation = transition_judgment_remediation_status(
        remediation,
        target_status="closed",
        changed_at="2026-03-30T01:15:00Z",
        changed_by_role="control_plane",
        rationale="closure artifact approved",
    )

    reinstatement = build_judgment_progression_reinstatement_record(
        closure_record=closure,
        affected_scope={
            "run_id": result["judgment_control_escalation_record"]["trace"]["run_id"],
            "trace_id": result["judgment_control_escalation_record"]["trace"]["trace_id"],
            "scope": "judgment_run",
            "artifact_id": result["judgment_control_escalation_record"]["artifact_id"],
        },
        reinstatement_type=reinstatement_type,
        required_gates_satisfied=["remediation_closed", "closure_approved", "approval_record_present"],
        approved_by_role="release_manager",
        approved_at="2026-03-30T01:16:00Z",
        resulting_next_allowed_state=next_state,
    )
    return remediation, closure, reinstatement


def test_allow_escalation_emits_action_and_outcome_and_allows_progression() -> None:
    result = run_judgment_learning_control_loop(**_inputs())
    assert result["decision"] == "allow"
    assert result["judgment_enforcement_action_record"]["action_type"] == "promote_or_continue"
    assert result["judgment_enforcement_outcome_record"]["progression_status"] == "allowed"
    assert result["progression_allowed"] is True


def test_warn_path_emits_warning_action_and_operator_remediation_for_policy_required_warning() -> None:
    inputs = _inputs()
    inputs["judgment_calibration_result"]["group_metrics"][0]["expected_calibration_error"] = 0.06
    result = run_judgment_learning_control_loop(**inputs)
    assert result["decision"] == "warn"
    assert result["judgment_enforcement_action_record"]["action_type"] == "continue_with_warning"
    assert result["judgment_operator_remediation_record"] is not None
    assert result["progression_allowed"] is False


def test_freeze_path_emits_freeze_action_and_prevents_progression() -> None:
    inputs = _inputs()
    inputs["judgment_drift_signal"]["group_signals"][0]["deltas"]["error_rate_delta"] = 0.06
    result = run_judgment_learning_control_loop(**inputs)
    assert result["decision"] == "freeze"
    assert result["judgment_enforcement_action_record"]["action_type"] == "freeze_pipeline_or_freeze_scope"
    assert result["judgment_enforcement_outcome_record"]["progression_status"] == "frozen"
    assert result["progression_allowed"] is False


def test_block_path_emits_block_action_and_prevents_progression() -> None:
    inputs = _inputs()
    inputs["judgment_error_budget_status"]["status"] = "exhausted"
    result = run_judgment_learning_control_loop(**inputs)
    assert result["decision"] == "block"
    assert result["judgment_enforcement_action_record"]["action_type"] == "block_artifact_or_block_progression"
    assert result["judgment_enforcement_outcome_record"]["progression_status"] == "prevented"
    assert result["progression_allowed"] is False


def test_missing_enforcement_action_artifact_fails_closed() -> None:
    result = run_judgment_learning_control_loop(**_inputs())
    traceability = evaluate_judgment_enforcement_traceability(
        escalation_record=result["judgment_control_escalation_record"],
        action_record=None,
        outcome_record=result["judgment_enforcement_outcome_record"],
        remediation_record=result["judgment_operator_remediation_record"],
    )
    assert traceability["progression_allowed"] is False
    assert "missing enforcement action artifact" in traceability["blocking_reasons"]


def test_missing_enforcement_outcome_artifact_fails_closed() -> None:
    result = run_judgment_learning_control_loop(**_inputs())
    traceability = evaluate_judgment_enforcement_traceability(
        escalation_record=result["judgment_control_escalation_record"],
        action_record=result["judgment_enforcement_action_record"],
        outcome_record=None,
        remediation_record=result["judgment_operator_remediation_record"],
    )
    assert traceability["progression_allowed"] is False
    assert "missing enforcement outcome artifact" in traceability["blocking_reasons"]


def test_remediation_lifecycle_rejects_invalid_jump() -> None:
    inputs = _inputs()
    inputs["judgment_error_budget_status"]["status"] = "exhausted"
    result = run_judgment_learning_control_loop(**inputs)
    remediation = result["judgment_operator_remediation_record"]

    try:
        transition_judgment_remediation_status(
            remediation,
            target_status="closed",
            changed_at="2026-03-30T01:00:00Z",
            changed_by_role="operator",
            rationale="invalid jump",
        )
        assert False, "expected invalid transition to raise"
    except ValueError as exc:
        assert "invalid remediation status transition" in str(exc)


def test_happy_path_freeze_remediation_closure_reinstatement_resumes_progression() -> None:
    inputs = _inputs()
    inputs["judgment_drift_signal"]["group_signals"][0]["deltas"]["error_rate_delta"] = 0.06
    result = run_judgment_learning_control_loop(**inputs)

    remediation, closure, reinstatement = _close_and_reinstate(
        result,
        reinstatement_type="unfreeze",
        next_state="allowed",
    )

    traceability = evaluate_judgment_enforcement_traceability(
        escalation_record=result["judgment_control_escalation_record"],
        action_record=result["judgment_enforcement_action_record"],
        outcome_record=result["judgment_enforcement_outcome_record"],
        remediation_record=remediation,
        closure_record=closure,
        reinstatement_record=reinstatement,
        evidence_artifact_refs=remediation["required_evidence_artifacts"],
        threshold_checks={
            "source_condition_addressed": True,
            "eval_thresholds_met": True,
            "drift_threshold_met": True,
        },
        policy_version="1.0.0",
    )
    assert traceability["progression_allowed"] is True


def test_missing_required_evidence_rejects_closure_and_progression_stays_blocked() -> None:
    inputs = _inputs()
    inputs["judgment_error_budget_status"]["status"] = "exhausted"
    result = run_judgment_learning_control_loop(**inputs)

    remediation = result["judgment_operator_remediation_record"]
    for state in ("in_progress", "evidence_submitted", "pending_review", "approved_for_closure"):
        remediation = transition_judgment_remediation_status(
            remediation,
            target_status=state,
            changed_at="2026-03-30T01:01:00Z",
            changed_by_role="operator",
            rationale="status progression",
        )

    closure = build_judgment_remediation_closure_record(
        remediation_record=remediation,
        escalation_record=result["judgment_control_escalation_record"],
        action_record=result["judgment_enforcement_action_record"],
        outcome_record=result["judgment_enforcement_outcome_record"],
        evidence_artifact_refs=["judgment_enforcement_outcome_record"],
        threshold_checks={"source_condition_addressed": False},
        policy_version="1.0.0",
        created_at="2026-03-30T01:14:00Z",
        approval_status="rejected",
        approval_actor_ref="",
        rationale="required evidence missing",
    )
    assert closure["closure_decision"] == "rejected"

    traceability = evaluate_judgment_enforcement_traceability(
        escalation_record=result["judgment_control_escalation_record"],
        action_record=result["judgment_enforcement_action_record"],
        outcome_record=result["judgment_enforcement_outcome_record"],
        remediation_record=remediation,
        closure_record=closure,
        evidence_artifact_refs=["judgment_enforcement_outcome_record"],
        threshold_checks={"source_condition_addressed": False},
        policy_version="1.0.0",
    )
    assert traceability["progression_allowed"] is False
    assert "remediation not closed" in traceability["blocking_reasons"]


def test_missing_closure_artifact_keeps_progression_frozen() -> None:
    inputs = _inputs()
    inputs["judgment_drift_signal"]["group_signals"][0]["deltas"]["error_rate_delta"] = 0.06
    result = run_judgment_learning_control_loop(**inputs)

    remediation = result["judgment_operator_remediation_record"]
    for state in ("in_progress", "evidence_submitted", "pending_review", "approved_for_closure", "closed"):
        remediation = transition_judgment_remediation_status(
            remediation,
            target_status=state,
            changed_at="2026-03-30T01:01:00Z",
            changed_by_role="operator",
            rationale="status progression",
        )

    traceability = evaluate_judgment_enforcement_traceability(
        escalation_record=result["judgment_control_escalation_record"],
        action_record=result["judgment_enforcement_action_record"],
        outcome_record=result["judgment_enforcement_outcome_record"],
        remediation_record=remediation,
    )
    assert traceability["progression_allowed"] is False
    assert "missing remediation closure artifact" in traceability["blocking_reasons"]


def test_missing_reinstatement_artifact_where_required_keeps_progression_blocked() -> None:
    inputs = _inputs()
    inputs["judgment_error_budget_status"]["status"] = "exhausted"
    result = run_judgment_learning_control_loop(**inputs)

    remediation, closure, _ = _close_and_reinstate(
        result,
        reinstatement_type="unblock",
        next_state="allowed",
    )

    traceability = evaluate_judgment_enforcement_traceability(
        escalation_record=result["judgment_control_escalation_record"],
        action_record=result["judgment_enforcement_action_record"],
        outcome_record=result["judgment_enforcement_outcome_record"],
        remediation_record=remediation,
        closure_record=closure,
        evidence_artifact_refs=remediation["required_evidence_artifacts"],
        threshold_checks={
            "source_condition_addressed": True,
            "eval_thresholds_met": True,
            "drift_threshold_met": True,
        },
        policy_version="1.0.0",
    )
    assert traceability["progression_allowed"] is False
    assert "missing progression reinstatement artifact" in traceability["blocking_reasons"]


def test_warn_required_remediation_requires_closure_and_warning_reinstatement() -> None:
    inputs = _inputs()
    inputs["judgment_calibration_result"]["group_metrics"][0]["expected_calibration_error"] = 0.06
    result = run_judgment_learning_control_loop(**inputs)

    remediation, closure, reinstatement = _close_and_reinstate(
        result,
        reinstatement_type="warning_acknowledged_continue",
        next_state="allowed_with_warning",
    )

    traceability = evaluate_judgment_enforcement_traceability(
        escalation_record=result["judgment_control_escalation_record"],
        action_record=result["judgment_enforcement_action_record"],
        outcome_record=result["judgment_enforcement_outcome_record"],
        remediation_record=remediation,
        closure_record=closure,
        reinstatement_record=reinstatement,
        evidence_artifact_refs=remediation["required_evidence_artifacts"],
        threshold_checks={
            "source_condition_addressed": True,
            "eval_thresholds_met": True,
            "drift_threshold_met": True,
        },
        policy_version="1.0.0",
    )
    assert traceability["progression_allowed"] is True


def test_deterministic_remediation_inputs_produce_same_closure_and_reinstatement_shape() -> None:
    inputs = _inputs()
    inputs["judgment_drift_signal"]["group_signals"][0]["deltas"]["error_rate_delta"] = 0.06
    first = run_judgment_learning_control_loop(**inputs)
    second = run_judgment_learning_control_loop(**inputs)

    first_remediation, first_closure, first_reinstatement = _close_and_reinstate(
        first,
        reinstatement_type="unfreeze",
        next_state="allowed",
    )
    second_remediation, second_closure, second_reinstatement = _close_and_reinstate(
        second,
        reinstatement_type="unfreeze",
        next_state="allowed",
    )

    assert first_remediation == second_remediation
    assert first_closure == second_closure
    assert first_reinstatement == second_reinstatement


def test_deterministic_escalation_input_produces_same_action_and_outcome_shape() -> None:
    first = run_judgment_learning_control_loop(**_inputs())
    second = run_judgment_learning_control_loop(**_inputs())
    assert first["judgment_enforcement_action_record"] == second["judgment_enforcement_action_record"]
    assert first["judgment_enforcement_outcome_record"] == second["judgment_enforcement_outcome_record"]
