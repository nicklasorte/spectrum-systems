"""Tests for VAL-04 control decision consistency validation."""

from __future__ import annotations

import copy
from typing import Any, Dict

import pytest

from spectrum_systems.contracts import load_example
from spectrum_systems.modules.governance.control_decision_consistency import (
    ControlDecisionConsistencyError,
    run_control_decision_consistency_validation,
)
def _eval_summary() -> Dict[str, Any]:
    return {
        "artifact_type": "eval_summary",
        "schema_version": "1.0.0",
        "trace_id": "11111111-1111-4111-8111-111111111111",
        "eval_run_id": "eval-run-001",
        "pass_rate": 0.95,
        "failure_rate": 0.05,
        "drift_rate": 0.05,
        "reproducibility_score": 0.95,
        "system_status": "healthy",
    }


def _error_budget(trace_id: str) -> Dict[str, Any]:
    budget = copy.deepcopy(load_example("error_budget_status"))
    budget["trace_refs"]["trace_id"] = trace_id
    budget["budget_status"] = "healthy"
    budget["highest_severity"] = "healthy"
    budget["triggered_conditions"] = []
    budget["reasons"] = []
    return budget


def _monitor_record() -> Dict[str, Any]:
    return {
        "monitor_record_id": "monitor-001",
        "source_run_id": "run-001",
        "source_suite_id": "suite-001",
        "created_at": "2026-03-28T00:00:00Z",
        "total_traces": 10,
        "passed_traces": 10,
        "failed_traces": 0,
        "pass_rate": 1.0,
        "average_reproducibility_score": 1.0,
        "drift_counts": {},
        "indeterminate_count": 0,
        "overall_status": "pass",
        "sli_snapshot": {
            "regression_pass_rate": 1.0,
            "drift_rate": 0.0,
            "average_reproducibility_score": 1.0,
        },
        "alert_recommendation": {"level": "none", "reasons": []},
        "metadata": {"schema_version": "1.0.0", "generator": "tests"},
    }


def _xrun(trace_id: str) -> Dict[str, Any]:
    return {
        "artifact_type": "cross_run_intelligence_decision",
        "schema_version": "2.0.0",
        "intelligence_id": "XRI-AAAAAAAAAAAA",
        "timestamp": "2026-03-28T00:00:00Z",
        "input_refs": {
            "replay_results": ["rpl-1"],
            "eval_summaries": ["eval-1"],
            "regression_results": ["reg-1"],
            "drift_results": ["drift-1"],
            "monitor_records": ["monitor-1"],
            "policy_ref": "policy://xrun/v1"
        },
        "aggregated_metrics": {
            "failure_rate_trend": 0.0,
            "drift_trend": 0.0,
            "regression_density": 0.0,
            "reproducibility_variance": 0.0
        },
        "detected_patterns": [],
        "recommended_actions": [],
        "system_signal": "stable",
        "trace_ids": [trace_id],
        "policy_version": "1.0.0"
    }


def _valid_input_refs() -> Dict[str, Any]:
    summary = _eval_summary()
    return {
        "eval_summaries": [summary],
        "error_budget_statuses": [_error_budget(summary["trace_id"])],
        "monitor_records": [_monitor_record()],
        "cross_run_intelligence_decisions": [_xrun(summary["trace_id"])],
        "policy_ref": {"policy_id": "policy-val04-v1"},
        "repeat_count": 3,
    }


def _case_map(result: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {case["case_id"]: case for case in result["validation_cases"]}


def test_identical_inputs_produce_identical_decisions() -> None:
    result = run_control_decision_consistency_validation(_valid_input_refs())
    case_map = _case_map(result)
    assert case_map["VAL04-A"]["passed"] is True
    assert case_map["VAL04-B"]["passed"] is True
    assert case_map["VAL04-C"]["passed"] is True


def test_borderline_threshold_inputs_are_still_deterministic() -> None:
    result = run_control_decision_consistency_validation(_valid_input_refs())
    case = _case_map(result)["VAL04-D"]
    assert case["passed"] is True
    assert case["actual_consistency"] is True


def test_malformed_input_fails_closed() -> None:
    result = run_control_decision_consistency_validation(_valid_input_refs())
    case = _case_map(result)["VAL04-E"]
    assert case["passed"] is True
    assert case["actual_consistency"] is True
    assert all(item["outcome"] == "error" for item in case["repeated_outputs"])


def test_divergence_causes_failed_final_status() -> None:
    import spectrum_systems.modules.governance.control_decision_consistency as mod

    valid = _valid_input_refs()
    original = mod.build_evaluation_control_decision
    counter = {"n": 0}

    def _diverging_build(payload: Dict[str, Any]) -> Dict[str, Any]:
        decision = original(payload)
        counter["n"] += 1
        if counter["n"] == 2:
            decision["system_response"] = "block"
        return decision

    mod.build_evaluation_control_decision = _diverging_build
    try:
        result = run_control_decision_consistency_validation(valid)
    finally:
        mod.build_evaluation_control_decision = original

    assert result["summary"]["divergence_detected"] is True
    assert result["final_status"] == "FAILED"


def test_hidden_state_flag_set_on_detected_divergence() -> None:
    import spectrum_systems.modules.governance.control_decision_consistency as mod

    valid = _valid_input_refs()
    original = mod.build_evaluation_control_decision
    counter = {"n": 0}

    def _diverging_build(payload: Dict[str, Any]) -> Dict[str, Any]:
        decision = original(payload)
        counter["n"] += 1
        if counter["n"] == 3:
            decision["triggered_signals"] = ["reliability_breach"]
        return decision

    mod.build_evaluation_control_decision = _diverging_build
    try:
        result = run_control_decision_consistency_validation(valid)
    finally:
        mod.build_evaluation_control_decision = original

    assert result["summary"]["hidden_state_suspected"] is True


def test_missing_required_input_rejected() -> None:
    with pytest.raises(ControlDecisionConsistencyError, match="eval_summaries"):
        run_control_decision_consistency_validation({})
