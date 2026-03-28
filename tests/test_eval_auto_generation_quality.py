"""Tests for VAL-07 eval auto-generation quality validation."""

from __future__ import annotations

from typing import Any, Dict

from spectrum_systems.modules.governance.eval_auto_generation_quality import (
    run_eval_auto_generation_quality_validation,
)


def _eval_summary(eval_run_id: str, failure_rate: float, drift_rate: float, reproducibility_score: float) -> Dict[str, Any]:
    return {
        "artifact_type": "eval_summary",
        "schema_version": "1.0.0",
        "trace_id": "11111111-1111-4111-8111-111111111111",
        "eval_run_id": eval_run_id,
        "pass_rate": round(1 - failure_rate, 6),
        "failure_rate": failure_rate,
        "drift_rate": drift_rate,
        "reproducibility_score": reproducibility_score,
        "system_status": "healthy",
    }


def _drift(artifact_id: str) -> Dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "artifact_type": "drift_detection_result",
        "schema_version": "1.1.0",
        "timestamp": "2026-03-28T00:00:00Z",
        "trace_refs": {"trace_id": "11111111-1111-4111-8111-111111111111"},
        "run_id": "run-1",
        "policy_id": "drift-policy-1",
        "baseline_id": "baseline-1",
        "baseline_source": "approved_replay_baseline",
        "comparison_target_id": "replay-1",
        "comparison_target_type": "replay_result",
        "drift_status": "no_drift",
        "compared_dimensions": [
            "final_status_delta",
            "enforcement_action_delta",
            "consistency_mismatch_delta",
            "drift_detected_delta",
            "failure_reason_present_delta",
        ],
        "metrics": {
            "final_status_delta": 0,
            "enforcement_action_delta": 0,
            "consistency_mismatch_delta": 0,
            "drift_detected_delta": 0,
            "failure_reason_present_delta": 0,
        },
        "triggered_thresholds": [],
        "reasons": ["none"],
        "generated_by_version": "drift_detection.py@1.0.0",
    }


def _monitor_record(record_id: str) -> Dict[str, Any]:
    return {
        "monitor_record_id": record_id,
        "source_run_id": "run-1",
        "source_suite_id": "suite-1",
        "created_at": "2026-03-28T00:00:00Z",
        "total_traces": 2,
        "passed_traces": 2,
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


def _regression(run_id: str, mismatch_count: int) -> Dict[str, Any]:
    results = []
    for i in range(4):
        mismatches = [{"field": "replay_final_status"}] if i < mismatch_count else []
        results.append(
            {
                "trace_id": f"trace-{i}",
                "comparison_digest": "a" * 64,
                "mismatch_summary": mismatches,
            }
        )
    return {"run_id": run_id, "suite_id": "suite-1", "results": results}


def _base_input_refs() -> Dict[str, Any]:
    return {
        "replay_results": [
            {"artifact_type": "replay_result", "replay_id": "replay-1", "trace_id": "11111111-1111-4111-8111-111111111111"},
            {"artifact_type": "replay_result", "replay_id": "replay-2", "trace_id": "11111111-1111-4111-8111-111111111111"},
        ],
        "eval_summaries": [
            _eval_summary("eval-1", failure_rate=0.10, drift_rate=0.02, reproducibility_score=0.95),
            _eval_summary("eval-2", failure_rate=0.12, drift_rate=0.03, reproducibility_score=0.94),
        ],
        "regression_results": [_regression("reg-1", mismatch_count=0), _regression("reg-2", mismatch_count=0)],
        "drift_results": [_drift("a" * 64), _drift("b" * 64)],
        "monitor_records": [_monitor_record("mr-1"), _monitor_record("mr-2")],
        "policy_ref": {"policy_id": "xrun-policy", "policy_version": "2026.03.28"},
    }


def _case_map(result: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {case["case_id"]: case for case in result["validation_cases"]}


def test_repeated_failure_generates_meaningful_executable_evals() -> None:
    result = run_eval_auto_generation_quality_validation(_base_input_refs())
    case = _case_map(result)["VAL07-A"]
    assert case["passed"] is True
    assert case["executable"] is True
    assert case["meaningful"] is True
    assert len(case["generated_eval_refs"]) >= 1


def test_drift_signal_generates_relevant_evals() -> None:
    result = run_eval_auto_generation_quality_validation(_base_input_refs())
    case = _case_map(result)["VAL07-B"]
    assert case["passed"] is True
    assert case["meaningful"] is True
    assert len(case["generated_eval_refs"]) >= 1


def test_regression_density_signal_generates_relevant_evals() -> None:
    result = run_eval_auto_generation_quality_validation(_base_input_refs())
    case = _case_map(result)["VAL07-C"]
    assert case["passed"] is True
    assert case["meaningful"] is True
    assert len(case["generated_eval_refs"]) >= 1


def test_stable_baseline_does_not_generate_eval_spam() -> None:
    result = run_eval_auto_generation_quality_validation(_base_input_refs())
    case = _case_map(result)["VAL07-D"]
    assert case["passed"] is True
    assert case["generated_eval_refs"] == []


def test_insufficient_input_fails_closed() -> None:
    result = run_eval_auto_generation_quality_validation(_base_input_refs())
    case = _case_map(result)["VAL07-E"]
    assert case["passed"] is True
    assert "fail_closed" in case["actual_properties"]


def test_malformed_input_fails_closed() -> None:
    result = run_eval_auto_generation_quality_validation(_base_input_refs())
    case = _case_map(result)["VAL07-F"]
    assert case["passed"] is True
    assert "fail_closed" in case["actual_properties"]


def test_non_executable_generated_evals_cause_failed_final_status(monkeypatch: Any) -> None:
    from spectrum_systems.modules.governance import eval_auto_generation_quality as quality_module

    monkeypatch.setattr(quality_module, "_is_eval_executable", lambda _eval_case: False)
    result = run_eval_auto_generation_quality_validation(_base_input_refs())

    assert result["final_status"] == "FAILED"
    assert result["summary"]["non_executable_eval_detected"] is True


def test_missed_generation_causes_failed_final_status(monkeypatch: Any) -> None:
    from spectrum_systems.modules.runtime import cross_run_intelligence as xrun_module

    original = xrun_module.generate_eval_cases_from_cross_run_intelligence
    monkeypatch.setattr(xrun_module, "generate_eval_cases_from_cross_run_intelligence", lambda _decision: [])
    try:
        result = run_eval_auto_generation_quality_validation(_base_input_refs())
    finally:
        monkeypatch.setattr(xrun_module, "generate_eval_cases_from_cross_run_intelligence", original)

    assert result["final_status"] == "FAILED"
    assert result["summary"]["missed_generation_detected"] is True
