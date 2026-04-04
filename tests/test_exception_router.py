from __future__ import annotations

import copy

import pytest

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.exception_router import (
    ExceptionRouterError,
    classify_exception_state,
    route_exception_resolution,
)


_BASE_KWARGS = {
    "source_artifact_ref": "roadmap_multi_batch_run_result:RMB-TEST00000001",
    "source_batch_id": "BATCH-I",
    "source_cycle_id": "RMB-TEST00000001",
    "control_decision": "allow",
    "autonomy_decision": "continue",
    "stop_reason": "execution_failed",
    "blocking_conditions": [],
    "drift_signals": {"drift_level": "low"},
    "replay_status": "match",
    "review_gate_status": "passed",
    "missing_eval_enforcement_artifacts": [],
    "unresolved_critical_risks": [],
    "failure_keys": ["EXECUTION_FAILED"],
    "created_at": "2026-04-04T00:00:00Z",
    "trace_id": "trace-exception-router-test",
}


def _classify(**overrides: object) -> dict:
    kwargs = copy.deepcopy(_BASE_KWARGS)
    kwargs.update(overrides)
    return classify_exception_state(**kwargs)


def test_classification_deterministic_for_same_inputs() -> None:
    first = _classify()
    second = _classify()
    assert first == second
    validate_artifact(first, "exception_classification_record")


def test_routing_deterministic_for_same_inputs() -> None:
    classification = _classify()
    first = route_exception_resolution(exception_classification_record=classification, created_at="2026-04-04T00:00:00Z")
    second = route_exception_resolution(exception_classification_record=classification, created_at="2026-04-04T00:00:00Z")
    assert first == second
    validate_artifact(first, "exception_resolution_record")


def test_missing_eval_coverage_routes_to_create_eval_batch() -> None:
    classification = _classify(failure_keys=["missing_eval_coverage"], stop_reason="eval_health_degraded")
    assert classification["exception_class"] == "missing_eval_coverage"
    resolution = route_exception_resolution(exception_classification_record=classification, created_at="2026-04-04T00:00:00Z")
    assert resolution["action_type"] == "create_eval_batch"


def test_replay_mismatch_routes_to_freeze_and_investigate() -> None:
    classification = _classify(replay_status="mismatch", stop_reason="replay_not_ready")
    resolution = route_exception_resolution(exception_classification_record=classification, created_at="2026-04-04T00:00:00Z")
    assert classification["exception_class"] == "replay_mismatch"
    assert resolution["action_type"] == "freeze_and_investigate"


def test_review_required_routes_to_queue_review() -> None:
    classification = _classify(review_gate_status="required", stop_reason="manual_review_required")
    resolution = route_exception_resolution(exception_classification_record=classification, created_at="2026-04-04T00:00:00Z")
    assert classification["exception_class"] == "review_required"
    assert resolution["action_type"] == "queue_review"


def test_policy_violation_routes_to_escalate() -> None:
    classification = _classify(failure_keys=["policy_violation:unsafe_transition"], stop_reason="contract_precondition_failed")
    resolution = route_exception_resolution(exception_classification_record=classification, created_at="2026-04-04T00:00:00Z")
    assert classification["exception_class"] == "policy_violation"
    assert resolution["action_type"] == "escalate"


def test_unresolved_critical_risk_routes_to_remediation_batch() -> None:
    classification = _classify(unresolved_critical_risks=["AUTH_CRITICAL_MISSING"], stop_reason="unresolved_blocker_persists")
    resolution = route_exception_resolution(exception_classification_record=classification, created_at="2026-04-04T00:00:00Z")
    assert classification["exception_class"] == "unresolved_critical_risk"
    assert resolution["action_type"] == "create_remediation_batch"


def test_malformed_required_inputs_fail_closed() -> None:
    with pytest.raises(ExceptionRouterError):
        _classify(drift_signals=None)


def test_unknown_blocker_does_not_silently_continue() -> None:
    classification = _classify(failure_keys=["NON_STANDARD_BLOCKER"], stop_reason="execution_blocked")
    resolution = route_exception_resolution(exception_classification_record=classification, created_at="2026-04-04T00:00:00Z")
    assert classification["exception_class"] in {"unknown_blocker", "execution_failure"}
    if classification["exception_class"] == "unknown_blocker":
        assert resolution["action_type"] == "stop_without_auto_action"
