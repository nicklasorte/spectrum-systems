"""Tests for governed evaluation_monitor migration to SRE-04 regression_result."""
from __future__ import annotations

import hashlib
import json
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.evaluation_monitor import (  # noqa: E402
    EvaluationMonitorError,
    InvalidRegressionResultError,
    InvalidReplayAnalysisError,
    assess_burn_rate,
    build_monitor_record,
    compute_alert_recommendation,
    run_evaluation_monitor,
    summarize_monitor_records,
    validate_replay_result_boundary_or_raise,
    validate_monitor_record,
    validate_monitor_summary,
)

_FIXTURE_DIR = _REPO_ROOT / "tests" / "fixtures" / "evaluation_monitor"
_HEALTHY_1 = _FIXTURE_DIR / "healthy_run_1.json"
_HEALTHY_2 = _FIXTURE_DIR / "healthy_run_2.json"
_DEGRADING_1 = _FIXTURE_DIR / "degrading_run_1.json"
_DEGRADING_2 = _FIXTURE_DIR / "degrading_run_2.json"
_CRITICAL_BURNRATE = _FIXTURE_DIR / "critical_burnrate_run.json"
_INVALID = _FIXTURE_DIR / "invalid_regression_result.json"


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _make_result(trace_id: str, *, passed: bool = True, indeterminate: bool = False) -> Dict[str, Any]:
    mismatch = [] if passed and not indeterminate else [
        {"field": "replay_final_status", "baseline_value": "allow", "current_value": "deny"}
    ]
    decision_status = "indeterminate" if indeterminate else ("consistent" if passed else "drifted")
    digest_payload = json.dumps({"trace_id": trace_id, "mismatch": mismatch}, sort_keys=True)
    return {
        "trace_id": trace_id,
        "replay_result_id": f"replay-{trace_id}",
        "analysis_id": str(uuid.uuid4()),
        "decision_status": decision_status,
        "reproducibility_score": 1.0 if passed else 0.0,
        "drift_type": "" if passed else "REGRESSION_MISMATCH",
        "passed": passed,
        "failure_reasons": [] if passed else ["deterministic replay comparison mismatch"],
        "baseline_replay_result_id": f"base-{trace_id}",
        "current_replay_result_id": f"replay-{trace_id}",
        "baseline_trace_id": trace_id,
        "current_trace_id": trace_id,
        "baseline_reference": f"replay_result:base-{trace_id}",
        "current_reference": f"replay_result:replay-{trace_id}",
        "mismatch_summary": mismatch,
        "comparison_digest": hashlib.sha256(digest_payload.encode("utf-8")).hexdigest(),
    }


def _make_run_result(*, run_id: str = "run-1", blocked: bool = False, regression_status: str = "pass", results: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    if results is None:
        results = [_make_result("t-1", passed=True), _make_result("t-2", passed=True)]
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed
    return {
        "artifact_type": "regression_result",
        "schema_version": "1.1.0",
        "blocked": blocked,
        "regression_status": regression_status,
        "run_id": run_id,
        "suite_id": "suite-1",
        "created_at": "2026-03-26T00:00:00Z",
        "total_traces": total,
        "passed_traces": passed,
        "failed_traces": failed,
        "pass_rate": (passed / total) if total else 0.0,
        "overall_status": "pass" if failed == 0 else "fail",
        "results": results,
        "summary": {
            "drift_counts": {},
            "average_reproducibility_score": sum(float(r["reproducibility_score"]) for r in results) / total if total else 0.0,
        },
    }


def _make_replay_analysis(status: str) -> Dict[str, Any]:
    return {
        "analysis_id": str(uuid.uuid4()),
        "trace_id": "trace-001",
        "replay_result_id": "replay-001",
        "original_decision": {"decision_status": "allow", "decision_reason_code": "orig"},
        "replay_decision": {"decision_status": "allow", "decision_reason_code": "replay"},
        "decision_consistency": {"status": status, "differences": []},
        "drift_type": None if status == "consistent" else "LOGIC_DRIFT",
        "reproducibility_score": 1.0 if status == "consistent" else 0.0,
        "explanation": "test",
        "created_at": "2026-03-26T00:00:00Z",
    }


def test_fixture_records_are_governed_and_schema_valid() -> None:
    for path in [_HEALTHY_1, _HEALTHY_2, _DEGRADING_1, _DEGRADING_2, _CRITICAL_BURNRATE]:
        record = build_monitor_record(_load_json(path))
        assert validate_monitor_record(record) == []


def test_build_monitor_record_derives_health_from_governed_fields() -> None:
    run = _make_run_result(regression_status="fail", blocked=True, results=[_make_result("t-1", passed=False)])
    run["overall_status"] = "pass"  # conflicting legacy field should be ignored
    run["pass_rate"] = 1.0

    rec = build_monitor_record(run)

    assert rec["overall_status"] == "fail"
    assert rec["pass_rate"] == 0.0
    assert rec["failed_traces"] == 1


def test_build_monitor_record_derives_drift_rate_from_mismatch_summary() -> None:
    run = _make_run_result(regression_status="fail", results=[_make_result("t-1", passed=False), _make_result("t-2", passed=True)])
    rec = build_monitor_record(run)
    assert rec["sli_snapshot"]["drift_rate"] == pytest.approx(0.5)


def test_build_monitor_record_rejects_invalid_governed_result() -> None:
    with pytest.raises(InvalidRegressionResultError):
        build_monitor_record(_load_json(_INVALID))


def test_build_monitor_record_requires_valid_comparison_digest() -> None:
    run = _make_run_result()
    run["results"][0]["comparison_digest"] = "bad"
    with pytest.raises(InvalidRegressionResultError, match="does not match"):
        build_monitor_record(run)


def test_build_monitor_record_require_replay_fail_closed() -> None:
    with pytest.raises(EvaluationMonitorError, match="required but was not provided"):
        build_monitor_record(_make_run_result(), replay_decision_analysis=None, require_replay=True)


def test_build_monitor_record_invalid_replay_rejected() -> None:
    with pytest.raises(InvalidReplayAnalysisError):
        build_monitor_record(_make_run_result(), replay_decision_analysis={"not": "valid"})


def test_build_monitor_record_uses_replay_analysis_when_provided() -> None:
    rec = build_monitor_record(_make_run_result(), replay_decision_analysis=_make_replay_analysis("drifted"))
    assert rec["sli_snapshot"]["replay_status"] == "drifted"
    assert rec["sli_snapshot"]["replay_consistency_sli"] == pytest.approx(0.0)


def test_compute_alert_recommendation_critical_on_fail_or_drift() -> None:
    alert = compute_alert_recommendation({"overall_status": "fail", "pass_rate": 0.5, "sli_snapshot": {"drift_rate": 0.1}})
    assert alert["level"] == "critical"


def test_burn_rate_and_summary_from_governed_records() -> None:
    records = [
        build_monitor_record(_load_json(_HEALTHY_1)),
        build_monitor_record(_load_json(_DEGRADING_1)),
        build_monitor_record(_load_json(_DEGRADING_2)),
    ]
    burn = assess_burn_rate(records)
    assert burn["status"] in {"elevated", "exhausting"}

    summary = summarize_monitor_records(records)
    assert validate_monitor_summary(summary) == []
    assert summary["aggregates"]["total_failed_runs"] >= 1


def test_run_evaluation_monitor_end_to_end() -> None:
    records, summary = run_evaluation_monitor([_HEALTHY_1, _HEALTHY_2])
    assert len(records) == 2
    assert validate_monitor_summary(summary) == []


def test_replay_boundary_rejects_non_replay_input() -> None:
    with pytest.raises(EvaluationMonitorError, match="replay_result failed validation"):
        validate_replay_result_boundary_or_raise({"artifact_type": "eval_summary"})


def test_replay_boundary_rejects_partial_replay() -> None:
    replay = _load_json(_REPO_ROOT / "contracts" / "examples" / "replay_result.json")
    replay.pop("error_budget_status", None)
    with pytest.raises(EvaluationMonitorError, match="missing required error_budget_status"):
        validate_replay_result_boundary_or_raise(replay)


def test_replay_boundary_rejects_observability_lineage_mismatch() -> None:
    replay = _load_json(_REPO_ROOT / "contracts" / "examples" / "replay_result.json")
    replay["error_budget_status"]["observability_metrics_id"] = "f" * 64
    with pytest.raises(EvaluationMonitorError, match="REPLAY_INVALID_LINEAGE"):
        validate_replay_result_boundary_or_raise(replay)


def test_replay_boundary_rejects_missing_observability_lineage_link() -> None:
    replay = _load_json(_REPO_ROOT / "contracts" / "examples" / "replay_result.json")
    replay["error_budget_status"].pop("observability_metrics_id", None)
    with pytest.raises(EvaluationMonitorError, match="failed validation|REPLAY_INVALID_LINEAGE"):
        validate_replay_result_boundary_or_raise(replay)
