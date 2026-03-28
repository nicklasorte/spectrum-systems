from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.cross_run_intelligence import (  # noqa: E402
    CrossRunIntelligenceError,
    run_cross_run_intelligence,
)


def _replay(trace_id: str, replay_id: str) -> dict:
    return {
        "artifact_type": "replay_result",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "replay_id": replay_id,
        "replay_run_id": f"run-{replay_id}",
        "timestamp": "2026-03-28T00:00:00Z",
        "input_artifact_reference": "eval_summary:src",
        "original_decision_reference": "evaluation_control_decision:orig",
        "original_enforcement_reference": "enforcement_result:orig",
        "replay_decision": "allow",
        "replay_enforcement_action": "allow",
        "replay_final_status": "consistent",
        "original_enforcement_action": "allow",
        "original_final_status": "consistent",
        "consistency_status": "match",
        "drift_detected": False,
        "provenance": {
            "source_artifact_type": "eval_summary",
            "source_artifact_id": "src-1",
            "replay_engine_version": "1.0.0",
        },
        "determinism_notes": [],
        "execution_notes": [],
        "observability_metrics": {
            "artifact_type": "observability_metrics",
            "schema_version": "1.0.0",
            "artifact_id": "obs-1",
            "timestamp": "2026-03-28T00:00:00Z",
            "trace_refs": {"trace_id": trace_id},
            "run_id": "run-1",
            "window": {"lookback_runs": 5},
            "metrics": {
                "error_rate": 0.0,
                "latency_p95_ms": 10.0,
                "latency_p99_ms": 20.0,
                "throughput_rps": 5.0,
                "drift_exceed_threshold_rate": 0.0,
                "replay_success_rate": 1.0,
                "coverage_ratio": 1.0,
                "policy_violation_rate": 0.0,
                "retry_rate": 0.0
            },
            "slo_thresholds": {
                "max_error_rate": 0.05,
                "max_latency_p95_ms": 500.0,
                "max_latency_p99_ms": 1000.0,
                "min_throughput_rps": 1.0,
                "max_drift_exceed_threshold_rate": 0.2,
                "min_replay_success_rate": 0.8,
                "min_coverage_ratio": 0.7,
                "max_policy_violation_rate": 0.1,
                "max_retry_rate": 0.1
            },
            "threshold_breaches": [],
            "metric_sources": {
                "error_rate": "replay_result",
                "latency_p95_ms": "replay_result",
                "latency_p99_ms": "replay_result",
                "throughput_rps": "replay_result",
                "drift_exceed_threshold_rate": "replay_result",
                "replay_success_rate": "replay_result",
                "coverage_ratio": "replay_result",
                "policy_violation_rate": "replay_result",
                "retry_rate": "replay_result"
            },
            "generated_by_version": "obs@1.0.0"
        },
        "error_budget_status": {
            "artifact_type": "error_budget_status",
            "schema_version": "1.0.0",
            "artifact_id": "ebs-1",
            "timestamp": "2026-03-28T00:00:00Z",
            "trace_refs": {"trace_id": trace_id},
            "run_id": "run-1",
            "budget_window": {"lookback_runs": 5},
            "sli_values": {
                "error_rate": 0.0,
                "latency_p95_ms": 10.0,
                "latency_p99_ms": 20.0,
                "throughput_rps": 5.0,
                "drift_exceed_threshold_rate": 0.0,
                "replay_success_rate": 1.0,
                "coverage_ratio": 1.0,
                "policy_violation_rate": 0.0,
                "retry_rate": 0.0
            },
            "burn_rates": {
                "error_rate": 0.0,
                "latency_p95_ms": 0.0,
                "latency_p99_ms": 0.0,
                "throughput_rps": 0.0,
                "drift_exceed_threshold_rate": 0.0,
                "replay_success_rate": 0.0,
                "coverage_ratio": 0.0,
                "policy_violation_rate": 0.0,
                "retry_rate": 0.0
            },
            "budget_status": "healthy",
            "triggered_dimensions": [],
            "policy_id": "ebp-1",
            "observability_metrics_id": "obs-1",
            "generated_by_version": "error_budget@1.0.0"
        }
    }


def _eval_summary(trace_id: str, eval_run_id: str, failure_rate: float, drift_rate: float, reproducibility: float) -> dict:
    return {
        "artifact_type": "eval_summary",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "eval_run_id": eval_run_id,
        "pass_rate": round(1 - failure_rate, 3),
        "failure_rate": failure_rate,
        "drift_rate": drift_rate,
        "reproducibility_score": reproducibility,
        "system_status": "healthy",
    }


def _drift(trace_id: str, artifact_id: str, status: str) -> dict:
    return {
        "artifact_id": artifact_id,
        "artifact_type": "drift_detection_result",
        "schema_version": "1.1.0",
        "timestamp": "2026-03-28T00:00:00Z",
        "trace_refs": {"trace_id": trace_id},
        "run_id": "run-1",
        "policy_id": "bgp-1",
        "baseline_id": "baseline-1",
        "baseline_source": "approved_replay_baseline",
        "comparison_target_id": "replay-1",
        "comparison_target_type": "replay_result",
        "drift_status": status,
        "compared_dimensions": [
            "final_status_delta",
            "enforcement_action_delta",
            "consistency_mismatch_delta",
            "drift_detected_delta",
            "failure_reason_present_delta"
        ],
        "metrics": {
            "final_status_delta": 0,
            "enforcement_action_delta": 0,
            "consistency_mismatch_delta": 0,
            "drift_detected_delta": 0,
            "failure_reason_present_delta": 0
        },
        "triggered_thresholds": [],
        "reasons": ["none"],
        "generated_by_version": "drift_detection.py@1.0.0"
    }


def _monitor_record() -> dict:
    return {
        "monitor_record_id": "mr-1",
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
        "metadata": {"schema_version": "1.0.0", "generator": "test"},
    }


def _regression(mismatch_count: int) -> dict:
    results = []
    for i in range(3):
        mismatch_summary = [] if i >= mismatch_count else [{"field": "replay_final_status"}]
        results.append(
            {
                "trace_id": f"t-{i}",
                "comparison_digest": "a" * 64,
                "mismatch_summary": mismatch_summary,
                "passed": len(mismatch_summary) == 0,
            }
        )
    return {"run_id": "reg-1", "suite_id": "suite-1", "results": results}


def _inputs() -> dict:
    trace = "11111111-1111-4111-8111-111111111111"
    return {
        "replay_results": [_replay(trace, "rp-1"), _replay(trace, "rp-2")],
        "eval_summaries": [
            _eval_summary(trace, "ev-1", 0.1, 0.1, 0.95),
            _eval_summary(trace, "ev-2", 0.1, 0.1, 0.95),
        ],
        "regression_results": [_regression(0), _regression(0)],
        "drift_results": [_drift(trace, "d" + "1" * 63, "no_drift"), _drift(trace, "d" + "2" * 63, "no_drift")],
        "monitor_records": [_monitor_record(), _monitor_record()],
        "policy_ref": {"policy_id": "xrun-policy", "policy_version": "2026.03.28"},
    }


def test_stable_scenario_no_action() -> None:
    result = run_cross_run_intelligence(_inputs())
    decision = result["cross_run_intelligence_decision"]
    assert decision["system_signal"] == "stable"
    assert decision["recommended_actions"] == []
    assert result["generated_eval_cases"] == []


def test_repeated_failure_triggers_eval_generation() -> None:
    payload = _inputs()
    payload["eval_summaries"][1]["failure_rate"] = 0.45
    payload["eval_summaries"][1]["pass_rate"] = 0.55
    result = run_cross_run_intelligence(payload)
    decision = result["cross_run_intelligence_decision"]
    assert "recurring_failure_type" in decision["detected_patterns"]
    assert "generate_eval_cases" in decision["recommended_actions"]
    assert len(result["generated_eval_cases"]) >= 1


def test_drift_trend_produces_warning_signal() -> None:
    payload = _inputs()
    payload["eval_summaries"][1]["drift_rate"] = 0.4
    result = run_cross_run_intelligence(payload)
    decision = result["cross_run_intelligence_decision"]
    assert decision["system_signal"] == "warning"
    assert "drift_cluster" in decision["detected_patterns"]


def test_regression_cluster_is_flagged() -> None:
    payload = _inputs()
    payload["regression_results"] = [_regression(2), _regression(2)]
    result = run_cross_run_intelligence(payload)
    decision = result["cross_run_intelligence_decision"]
    assert decision["aggregated_metrics"]["regression_density"] > 0.3
    assert "unstable_module" in decision["detected_patterns"]


def test_missing_input_fails_closed() -> None:
    payload = _inputs()
    del payload["drift_results"]
    with pytest.raises(CrossRunIntelligenceError):
        run_cross_run_intelligence(payload)


def test_malformed_schema_fails_closed() -> None:
    payload = _inputs()
    payload["eval_summaries"][0] = {"artifact_type": "eval_summary"}
    with pytest.raises(CrossRunIntelligenceError):
        run_cross_run_intelligence(payload)
