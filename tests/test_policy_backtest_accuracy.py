from __future__ import annotations

import copy

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.governance import policy_backtest_accuracy as val05
from spectrum_systems.modules.governance.policy_backtest_accuracy import run_policy_backtest_accuracy


def _input_refs() -> dict:
    replay = copy.deepcopy(load_example("replay_result"))
    eval_summary = copy.deepcopy(load_example("eval_summary"))
    budget = copy.deepcopy(load_example("error_budget_status"))
    trace_id = "11111111-1111-4111-8111-111111111111"
    replay["trace_id"] = trace_id
    replay["timestamp"] = "2026-03-28T00:00:00Z"
    replay["replay_id"] = "rp-val05-test"
    replay["replay_run_id"] = "run-rp-val05-test"
    replay["consistency_status"] = "match"
    replay["drift_detected"] = False
    replay["observability_metrics"]["trace_refs"]["trace_id"] = trace_id
    replay["error_budget_status"]["trace_refs"]["trace_id"] = trace_id

    eval_summary["trace_id"] = trace_id
    eval_summary["eval_run_id"] = "eval-val05-test"

    budget["trace_refs"]["trace_id"] = trace_id
    budget["budget_status"] = "healthy"

    xrun = {
        "artifact_type": "cross_run_intelligence_decision",
        "schema_version": "2.0.0",
        "intelligence_id": "XRI-1234ABCDEF56",
        "timestamp": "2026-03-28T00:00:00Z",
        "input_refs": {
            "replay_results": ["rp-val05-test"],
            "eval_summaries": ["eval-val05-test"],
            "regression_results": ["reg-1"],
            "drift_results": ["drift-1"],
            "monitor_records": ["monitor-1"],
            "policy_ref": "policy-v1",
        },
        "aggregated_metrics": {
            "failure_rate_trend": 0.0,
            "drift_trend": 0.0,
            "regression_density": 0.0,
            "reproducibility_variance": 0.0,
        },
        "detected_patterns": [],
        "recommended_actions": [],
        "system_signal": "stable",
        "trace_ids": [trace_id],
        "policy_version": "2026.03.28",
    }

    baseline = {
        "policy_id": "policy-baseline",
        "policy_version": "v1",
        "thresholds": {
            "reliability_threshold": 0.8,
            "drift_threshold": 0.2,
            "trust_threshold": 0.8,
        },
    }

    return {
        "replay_results": [replay],
        "eval_summaries": [eval_summary],
        "error_budget_statuses": [budget],
        "cross_run_intelligence_decisions": [xrun],
        "baseline_policy_ref": baseline,
    }


def _case(result: dict, case_type: str) -> dict:
    for case in result["validation_cases"]:
        if case["case_type"] == case_type:
            return case
    raise AssertionError(f"missing case_type={case_type}")


def test_identical_policy_produces_safe_no_change_outcome() -> None:
    result = run_policy_backtest_accuracy(_input_refs())
    case = _case(result, "identical_policy_no_change")
    assert case["actual_recommendation"] in {"accept_policy", "require_review"}
    assert case["actual_risks"] == []


def test_improvement_case_accepted() -> None:
    result = run_policy_backtest_accuracy(_input_refs())
    assert _case(result, "candidate_improves_without_new_risk")["actual_recommendation"] == "accept_policy"


def test_missed_failure_case_rejected() -> None:
    result = run_policy_backtest_accuracy(_input_refs())
    case = _case(result, "candidate_introduces_missed_failure")
    assert case["actual_recommendation"] == "reject_policy"
    assert "missed_failures" in case["actual_risks"]


def test_overblocking_case_rejected() -> None:
    result = run_policy_backtest_accuracy(_input_refs())
    case = _case(result, "candidate_overblocks_significantly")
    assert case["actual_recommendation"] == "reject_policy"
    assert "overblocking" in case["actual_risks"]


def test_mixed_case_requires_review() -> None:
    result = run_policy_backtest_accuracy(_input_refs())
    assert _case(result, "mixed_delta_requires_review")["actual_recommendation"] == "require_review"


def test_malformed_policy_fails_closed() -> None:
    result = run_policy_backtest_accuracy(_input_refs())
    case = _case(result, "malformed_candidate_policy")
    assert case["actual_recommendation"] == "fail_closed"
    assert case["passed"] is True


def test_inconsistent_inputs_fail_closed() -> None:
    result = run_policy_backtest_accuracy(_input_refs())
    case = _case(result, "inconsistent_input_bundle")
    assert case["actual_recommendation"] == "fail_closed"
    assert case["passed"] is True


def test_any_false_accept_causes_failed_final_status(monkeypatch) -> None:
    original_execute_case = val05._execute_case

    def _force_false_accept(case_type: str, payload: dict, expected: dict) -> dict:
        case = original_execute_case(case_type, payload, expected)
        if case_type == "candidate_introduces_missed_failure":
            case["actual_recommendation"] = "accept_policy"
            case["passed"] = False
            case["blocking_reason"] = "synthetic false-accept injection"
        return case

    monkeypatch.setattr(val05, "_execute_case", _force_false_accept)
    result = run_policy_backtest_accuracy(_input_refs())
    assert result["summary"]["false_accept_detected"] is True
    assert result["final_status"] == "FAILED"
    validate_artifact(result, "policy_backtest_accuracy_result")
