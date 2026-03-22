"""Tests for BS — Continuous Evaluation Monitor (evaluation_monitor.py).

Covers:
 1.  valid monitor record creation from a healthy regression_run_result
 2.  invalid regression input rejection (schema validation failure)
 3.  correct drift-rate computation
 4.  trend classification: improving / stable / degrading
 5.  burn-rate classification: normal / elevated / exhausting
 6.  warning alert recommendation
 7.  critical alert recommendation (pass_rate below threshold)
 8.  critical alert recommendation (drift_rate above threshold)
 9.  summary aggregation correctness
10.  summary trend analysis
11.  recommended_action derivation (none, watch, freeze_changes, rollback_candidate)
12.  CLI exit code 0 — healthy
13.  CLI exit code 1 — warning / degrading
14.  CLI exit code 2 — critical alert / exhausting burn rate
15.  CLI exit code 2 — invalid input
16.  schema validation for all produced artifacts
17.  run_evaluation_monitor raises on empty path list
18.  run_evaluation_monitor raises on missing file
19.  validate_monitor_record returns empty list for valid record
20.  validate_monitor_summary returns empty list for valid summary
21.  indeterminate trace count is correct
"""
from __future__ import annotations

import json
import sys
import uuid
from copy import deepcopy
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
    classify_trend,
    compute_alert_recommendation,
    run_evaluation_monitor,
    summarize_monitor_records,
    validate_monitor_record,
    validate_monitor_summary,
)

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------

_FIXTURE_DIR = _REPO_ROOT / "tests" / "fixtures" / "evaluation_monitor"
_HEALTHY_1 = _FIXTURE_DIR / "healthy_run_1.json"
_HEALTHY_2 = _FIXTURE_DIR / "healthy_run_2.json"
_DEGRADING_1 = _FIXTURE_DIR / "degrading_run_1.json"
_DEGRADING_2 = _FIXTURE_DIR / "degrading_run_2.json"
_INVALID = _FIXTURE_DIR / "invalid_regression_result.json"
_CRITICAL_BURNRATE = _FIXTURE_DIR / "critical_burnrate_run.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _make_run_result(
    *,
    run_id: str = "run-test-001",
    suite_id: str = "suite-test-001",
    total_traces: int = 4,
    passed_traces: int = 4,
    failed_traces: int = 0,
    pass_rate: float = 1.0,
    overall_status: str = "pass",
    results: List[Dict[str, Any]] | None = None,
    avg_repro: float = 0.9,
    drift_counts: Dict[str, int] | None = None,
) -> Dict[str, Any]:
    if results is None:
        results = [
            {
                "trace_id": f"trace-{i:03d}",
                "replay_result_id": f"replay-{i:03d}",
                "analysis_id": f"analysis-{i:03d}",
                "decision_status": "consistent",
                "reproducibility_score": avg_repro,
                "drift_type": "",
                "passed": True,
                "failure_reasons": [],
            }
            for i in range(1, total_traces + 1)
        ]
    if drift_counts is None:
        drift_counts = {}
    return {
        "run_id": run_id,
        "suite_id": suite_id,
        "created_at": "2025-01-01T00:00:00Z",
        "total_traces": total_traces,
        "passed_traces": passed_traces,
        "failed_traces": failed_traces,
        "pass_rate": pass_rate,
        "overall_status": overall_status,
        "results": results,
        "summary": {
            "drift_counts": drift_counts,
            "average_reproducibility_score": avg_repro,
        },
    }


# ---------------------------------------------------------------------------
# 1. Valid monitor record creation
# ---------------------------------------------------------------------------


def test_build_monitor_record_healthy():
    run_result = _load_json(_HEALTHY_1)
    record = build_monitor_record(run_result)

    assert record["source_run_id"] == run_result["run_id"]
    assert record["source_suite_id"] == run_result["suite_id"]
    assert record["total_traces"] == run_result["total_traces"]
    assert record["passed_traces"] == run_result["passed_traces"]
    assert record["failed_traces"] == run_result["failed_traces"]
    assert record["pass_rate"] == run_result["pass_rate"]
    assert record["overall_status"] == run_result["overall_status"]
    assert record["alert_recommendation"]["level"] == "none"


def test_build_monitor_record_schema_valid():
    run_result = _load_json(_HEALTHY_1)
    record = build_monitor_record(run_result)
    errors = validate_monitor_record(record)
    assert errors == [], f"Schema errors: {errors}"


def test_build_monitor_record_has_metadata():
    run_result = _make_run_result()
    record = build_monitor_record(run_result)
    assert "schema_version" in record["metadata"]
    assert "generator" in record["metadata"]


# ---------------------------------------------------------------------------
# 2. Invalid regression input rejection
# ---------------------------------------------------------------------------


def test_invalid_regression_result_raises():
    invalid = _load_json(_INVALID)
    with pytest.raises(InvalidRegressionResultError):
        build_monitor_record(invalid)


def test_invalid_regression_missing_field():
    run_result = _make_run_result()
    del run_result["results"]
    with pytest.raises(InvalidRegressionResultError):
        build_monitor_record(run_result)


# ---------------------------------------------------------------------------
# 3. Drift-rate computation
# ---------------------------------------------------------------------------


def test_drift_rate_zero_for_all_consistent():
    run_result = _make_run_result()
    record = build_monitor_record(run_result)
    assert record["sli_snapshot"]["drift_rate"] == 0.0


def test_drift_rate_correct_for_partial_drift():
    # 2 out of 4 traces are drifted
    results = [
        {
            "trace_id": "trace-001",
            "replay_result_id": "r-001",
            "analysis_id": "a-001",
            "decision_status": "drifted",
            "reproducibility_score": 0.6,
            "drift_type": "semantic_drift",
            "passed": False,
            "failure_reasons": ["drift"],
        },
        {
            "trace_id": "trace-002",
            "replay_result_id": "r-002",
            "analysis_id": "a-002",
            "decision_status": "drifted",
            "reproducibility_score": 0.6,
            "drift_type": "semantic_drift",
            "passed": False,
            "failure_reasons": ["drift"],
        },
        {
            "trace_id": "trace-003",
            "replay_result_id": "r-003",
            "analysis_id": "a-003",
            "decision_status": "consistent",
            "reproducibility_score": 0.9,
            "drift_type": "",
            "passed": True,
            "failure_reasons": [],
        },
        {
            "trace_id": "trace-004",
            "replay_result_id": "r-004",
            "analysis_id": "a-004",
            "decision_status": "consistent",
            "reproducibility_score": 0.9,
            "drift_type": "",
            "passed": True,
            "failure_reasons": [],
        },
    ]
    run_result = _make_run_result(
        total_traces=4,
        passed_traces=2,
        failed_traces=2,
        pass_rate=0.5,
        overall_status="fail",
        results=results,
    )
    record = build_monitor_record(run_result)
    assert record["sli_snapshot"]["drift_rate"] == pytest.approx(0.5)


def test_drift_rate_zero_total_traces():
    """When total_traces=0, drift_rate should be 0.0 (no division by zero)."""
    run_result = _make_run_result(
        total_traces=0,
        passed_traces=0,
        failed_traces=0,
        pass_rate=0.0,
        results=[],
    )
    record = build_monitor_record(run_result)
    assert record["sli_snapshot"]["drift_rate"] == 0.0


# ---------------------------------------------------------------------------
# 4. Trend classification
# ---------------------------------------------------------------------------


def test_classify_trend_improving():
    assert classify_trend([0.5, 0.6, 0.7, 0.8]) == "improving"


def test_classify_trend_degrading():
    assert classify_trend([0.8, 0.7, 0.6, 0.5]) == "degrading"


def test_classify_trend_stable_equal():
    assert classify_trend([0.8, 0.8, 0.8]) == "stable"


def test_classify_trend_stable_mixed():
    # Mixed direction → conservative "stable"
    assert classify_trend([0.8, 0.6, 0.9]) == "stable"


def test_classify_trend_single_value():
    assert classify_trend([0.5]) == "stable"


def test_classify_trend_empty():
    assert classify_trend([]) == "stable"


def test_classify_trend_two_improving():
    assert classify_trend([0.5, 0.9]) == "improving"


def test_classify_trend_two_degrading():
    assert classify_trend([0.9, 0.5]) == "degrading"


# ---------------------------------------------------------------------------
# 5. Burn-rate classification
# ---------------------------------------------------------------------------


def test_burn_rate_normal():
    records = [
        _make_run_result(overall_status="pass"),
        _make_run_result(run_id="run-002", overall_status="pass"),
        _make_run_result(run_id="run-003", overall_status="pass"),
        _make_run_result(run_id="run-004", overall_status="pass"),
    ]
    monitor_records = [build_monitor_record(r) for r in records]
    result = assess_burn_rate(monitor_records)
    assert result["status"] == "normal"


def test_burn_rate_elevated():
    # 1/4 = 0.25 >= elevated threshold (0.25)
    records = [
        _make_run_result(overall_status="pass"),
        _make_run_result(run_id="run-002", overall_status="pass"),
        _make_run_result(run_id="run-003", overall_status="pass"),
        _make_run_result(
            run_id="run-004",
            overall_status="fail",
            passed_traces=3,
            failed_traces=1,
            pass_rate=0.75,
        ),
    ]
    monitor_records = [build_monitor_record(r) for r in records]
    result = assess_burn_rate(monitor_records)
    assert result["status"] == "elevated"


def test_burn_rate_exhausting():
    # 2/4 = 0.5 >= exhausting threshold (0.5)
    records = [
        _make_run_result(overall_status="pass"),
        _make_run_result(run_id="run-002", overall_status="pass"),
        _make_run_result(
            run_id="run-003",
            overall_status="fail",
            passed_traces=3,
            failed_traces=1,
            pass_rate=0.75,
        ),
        _make_run_result(
            run_id="run-004",
            overall_status="fail",
            passed_traces=3,
            failed_traces=1,
            pass_rate=0.75,
        ),
    ]
    monitor_records = [build_monitor_record(r) for r in records]
    result = assess_burn_rate(monitor_records)
    assert result["status"] == "exhausting"


def test_burn_rate_empty_records():
    with pytest.raises(EvaluationMonitorError, match="at least one record"):
        assess_burn_rate([])


# ---------------------------------------------------------------------------
# 6. Warning alert recommendation
# ---------------------------------------------------------------------------


def test_alert_warning_for_failed_run_above_critical_threshold():
    # overall_status=fail but pass_rate >= 0.8 → warning (not critical)
    run_result = _make_run_result(
        overall_status="fail",
        passed_traces=4,
        failed_traces=1,
        pass_rate=0.8,
    )
    record = build_monitor_record(run_result)
    assert record["alert_recommendation"]["level"] == "warning"


# ---------------------------------------------------------------------------
# 7. Critical alert — pass_rate below threshold
# ---------------------------------------------------------------------------


def test_alert_critical_for_failed_run_below_threshold():
    run_result = _load_json(_DEGRADING_2)
    record = build_monitor_record(run_result)
    assert record["alert_recommendation"]["level"] == "critical"
    assert any("pass_rate" in r for r in record["alert_recommendation"]["reasons"])


def test_alert_critical_threshold_override():
    run_result = _make_run_result(
        overall_status="fail",
        passed_traces=9,
        failed_traces=1,
        pass_rate=0.9,
    )
    # With a very high critical_pass_rate threshold, even 0.9 triggers critical
    record_partial = {
        "overall_status": "fail",
        "pass_rate": 0.9,
        "sli_snapshot": {"drift_rate": 0.0, "average_reproducibility_score": 0.9},
    }
    alert = compute_alert_recommendation(
        record_partial, thresholds={"critical_pass_rate": 0.95}
    )
    assert alert["level"] == "critical"


# ---------------------------------------------------------------------------
# 8. Critical alert — drift_rate above threshold
# ---------------------------------------------------------------------------


def test_alert_critical_for_high_drift_rate():
    run_result = _load_json(_CRITICAL_BURNRATE)
    record = build_monitor_record(run_result)
    assert record["alert_recommendation"]["level"] == "critical"
    assert any("drift_rate" in r for r in record["alert_recommendation"]["reasons"])


def test_alert_critical_drift_threshold_override():
    record_partial = {
        "overall_status": "pass",
        "pass_rate": 1.0,
        "sli_snapshot": {"drift_rate": 0.05, "average_reproducibility_score": 0.9},
    }
    alert = compute_alert_recommendation(
        record_partial, thresholds={"critical_drift_rate": 0.01}
    )
    assert alert["level"] == "critical"
    assert any("drift_rate" in r for r in alert["reasons"])


@pytest.mark.parametrize(
    "partial_record",
    [
        {},
        {"overall_status": "pass", "sli_snapshot": {"drift_rate": 0.0}},
        {"pass_rate": 1.0, "sli_snapshot": {"drift_rate": 0.0}},
        {"overall_status": "pass", "pass_rate": 1.0},
    ],
)
def test_compute_alert_recommendation_partial_input_raises(partial_record):
    with pytest.raises(EvaluationMonitorError, match="missing required field"):
        compute_alert_recommendation(partial_record)


def test_compute_alert_recommendation_invalid_sli_snapshot_raises():
    with pytest.raises(EvaluationMonitorError, match="drift_rate"):
        compute_alert_recommendation(
            {
                "overall_status": "pass",
                "pass_rate": 1.0,
                "sli_snapshot": {},
            }
        )


# ---------------------------------------------------------------------------
# 9. Summary aggregation correctness
# ---------------------------------------------------------------------------


def test_summary_aggregates_correctly():
    run1 = _make_run_result(run_id="r1", pass_rate=1.0, overall_status="pass")
    run2 = _make_run_result(
        run_id="r2",
        pass_rate=0.5,
        overall_status="fail",
        passed_traces=2,
        failed_traces=2,
    )
    records = [build_monitor_record(run1), build_monitor_record(run2)]
    summary = summarize_monitor_records(records)

    assert summary["aggregates"]["average_pass_rate"] == pytest.approx(0.75)
    assert summary["aggregates"]["total_failed_runs"] == 1
    assert summary["window"]["total_runs"] == 2
    assert sorted(summary["source_run_ids"]) == ["r1", "r2"]


def test_summary_schema_valid():
    records = [
        build_monitor_record(_load_json(_HEALTHY_1)),
        build_monitor_record(_load_json(_HEALTHY_2)),
    ]
    summary = summarize_monitor_records(records)
    errors = validate_monitor_summary(summary)
    assert errors == [], f"Schema errors: {errors}"


def test_summary_empty_records_raises():
    with pytest.raises(EvaluationMonitorError):
        summarize_monitor_records([])


# ---------------------------------------------------------------------------
# 10. Summary trend analysis
# ---------------------------------------------------------------------------


def test_summary_trend_degrading_sequence():
    records = [
        build_monitor_record(_load_json(_HEALTHY_1)),
        build_monitor_record(_load_json(_HEALTHY_2)),
        build_monitor_record(_load_json(_DEGRADING_1)),
        build_monitor_record(_load_json(_DEGRADING_2)),
    ]
    summary = summarize_monitor_records(records)
    assert summary["trend_analysis"]["pass_rate_trend"] == "degrading"


def test_summary_trend_stable_for_consistent_healthy():
    records = [
        build_monitor_record(_load_json(_HEALTHY_1)),
        build_monitor_record(_load_json(_HEALTHY_2)),
    ]
    summary = summarize_monitor_records(records)
    assert summary["trend_analysis"]["pass_rate_trend"] == "stable"


# ---------------------------------------------------------------------------
# 11. Recommended action derivation
# ---------------------------------------------------------------------------


def test_recommended_action_none_for_healthy():
    records = [
        build_monitor_record(_load_json(_HEALTHY_1)),
        build_monitor_record(_load_json(_HEALTHY_2)),
    ]
    summary = summarize_monitor_records(records)
    assert summary["recommended_action"] == "none"


def test_recommended_action_watch_for_degrading():
    records = [
        build_monitor_record(_load_json(_HEALTHY_1)),
        build_monitor_record(_load_json(_HEALTHY_2)),
        build_monitor_record(_load_json(_DEGRADING_1)),
        build_monitor_record(_load_json(_DEGRADING_2)),
    ]
    summary = summarize_monitor_records(records)
    # Degrading trend + possible critical alerts → rollback_candidate or watch
    assert summary["recommended_action"] in ("watch", "rollback_candidate", "freeze_changes")


def test_recommended_action_freeze_for_elevated_burn():
    # Create enough failed runs to trigger elevated burn rate (1/4 = 25%)
    # Use pass_rate=0.85 (above critical threshold of 0.8) so only a warning
    # alert is emitted — no critical alert, no degrading trend → freeze_changes
    run_pass = _make_run_result(run_id="r1", overall_status="pass", pass_rate=0.85, avg_repro=0.85)
    run_pass2 = _make_run_result(run_id="r2", overall_status="pass", pass_rate=0.85, avg_repro=0.85)
    run_pass3 = _make_run_result(run_id="r3", overall_status="pass", pass_rate=0.85, avg_repro=0.85)
    run_fail = _make_run_result(
        run_id="r4",
        overall_status="fail",
        passed_traces=3,
        failed_traces=1,
        pass_rate=0.85,
        avg_repro=0.85,
    )
    records = [
        build_monitor_record(run_pass),
        build_monitor_record(run_pass2),
        build_monitor_record(run_pass3),
        build_monitor_record(run_fail),
    ]
    summary = summarize_monitor_records(records)
    # 1 out of 4 failed → elevated burn rate; no critical alerts → freeze_changes
    assert summary["recommended_action"] == "freeze_changes"


# ---------------------------------------------------------------------------
# 12. CLI exit code 0 — healthy
# ---------------------------------------------------------------------------


def test_cli_exit_0_healthy(tmp_path):
    from scripts.run_evaluation_monitor import main

    exit_code = main([
        "--input", str(_HEALTHY_1),
        "--input", str(_HEALTHY_2),
        "--output-dir", str(tmp_path),
    ])
    assert exit_code == 0
    assert (tmp_path / "evaluation_monitor_summary.json").exists()
    assert (tmp_path / "evaluation_monitor_record_1.json").exists()
    assert (tmp_path / "evaluation_monitor_record_2.json").exists()


# ---------------------------------------------------------------------------
# 13. CLI exit code 1 — warning / degrading
# ---------------------------------------------------------------------------


def test_cli_exit_1_degrading(tmp_path):
    from scripts.run_evaluation_monitor import main

    exit_code = main([
        "--input", str(_HEALTHY_1),
        "--input", str(_HEALTHY_2),
        "--input", str(_DEGRADING_1),
        "--input", str(_DEGRADING_2),
        "--output-dir", str(tmp_path),
    ])
    assert exit_code in (1, 2)


# ---------------------------------------------------------------------------
# 14. CLI exit code 2 — critical alert / exhausting burn rate
# ---------------------------------------------------------------------------


def test_cli_exit_2_critical(tmp_path):
    from scripts.run_evaluation_monitor import main

    # Use the critical burnrate fixture
    exit_code = main([
        "--input", str(_CRITICAL_BURNRATE),
        "--output-dir", str(tmp_path),
    ])
    assert exit_code == 2


# ---------------------------------------------------------------------------
# 15. CLI exit code 2 — invalid input
# ---------------------------------------------------------------------------


def test_cli_exit_2_invalid_input(tmp_path):
    from scripts.run_evaluation_monitor import main

    exit_code = main([
        "--input", str(_INVALID),
        "--output-dir", str(tmp_path),
    ])
    assert exit_code == 2


def test_cli_exit_2_missing_file(tmp_path):
    from scripts.run_evaluation_monitor import main

    exit_code = main([
        "--input", str(tmp_path / "does_not_exist.json"),
        "--output-dir", str(tmp_path),
    ])
    assert exit_code == 2


# ---------------------------------------------------------------------------
# 16. Schema validation for all produced artifacts
# ---------------------------------------------------------------------------


def test_all_fixture_records_schema_valid():
    for fixture_path in [_HEALTHY_1, _HEALTHY_2, _DEGRADING_1, _DEGRADING_2, _CRITICAL_BURNRATE]:
        run_result = _load_json(fixture_path)
        record = build_monitor_record(run_result)
        errors = validate_monitor_record(record)
        assert errors == [], f"Schema errors for {fixture_path.name}: {errors}"


# ---------------------------------------------------------------------------
# 17. run_evaluation_monitor raises on empty path list
# ---------------------------------------------------------------------------


def test_run_evaluation_monitor_empty_raises():
    with pytest.raises(EvaluationMonitorError):
        run_evaluation_monitor([])


# ---------------------------------------------------------------------------
# 18. run_evaluation_monitor raises on missing file
# ---------------------------------------------------------------------------


def test_run_evaluation_monitor_missing_file():
    with pytest.raises(InvalidRegressionResultError):
        run_evaluation_monitor(["/tmp/nonexistent_file_xyz.json"])


# ---------------------------------------------------------------------------
# 19. validate_monitor_record returns empty list for valid record
# ---------------------------------------------------------------------------


def test_validate_monitor_record_valid():
    run_result = _load_json(_HEALTHY_1)
    record = build_monitor_record(run_result)
    errors = validate_monitor_record(record)
    assert errors == []


def test_validate_monitor_record_invalid():
    errors = validate_monitor_record({"not": "a valid record"})
    assert len(errors) > 0


# ---------------------------------------------------------------------------
# 20. validate_monitor_summary returns empty list for valid summary
# ---------------------------------------------------------------------------


def test_validate_monitor_summary_valid():
    records = [
        build_monitor_record(_load_json(_HEALTHY_1)),
        build_monitor_record(_load_json(_HEALTHY_2)),
    ]
    summary = summarize_monitor_records(records)
    errors = validate_monitor_summary(summary)
    assert errors == []


def test_validate_monitor_summary_invalid():
    errors = validate_monitor_summary({"not": "a valid summary"})
    assert len(errors) > 0


# ---------------------------------------------------------------------------
# 21. Indeterminate trace count is correct
# ---------------------------------------------------------------------------


def test_indeterminate_count_correct():
    results = [
        {
            "trace_id": "t1",
            "replay_result_id": "r1",
            "analysis_id": "a1",
            "decision_status": "indeterminate",
            "reproducibility_score": 0.5,
            "drift_type": "",
            "passed": False,
            "failure_reasons": ["indeterminate"],
        },
        {
            "trace_id": "t2",
            "replay_result_id": "r2",
            "analysis_id": "a2",
            "decision_status": "consistent",
            "reproducibility_score": 0.9,
            "drift_type": "",
            "passed": True,
            "failure_reasons": [],
        },
    ]
    run_result = _make_run_result(
        total_traces=2,
        passed_traces=1,
        failed_traces=1,
        pass_rate=0.5,
        overall_status="fail",
        results=results,
    )
    record = build_monitor_record(run_result)
    assert record["indeterminate_count"] == 1


# ---------------------------------------------------------------------------
# BX — Replay-to-Evaluation Integration tests (22–26)
# ---------------------------------------------------------------------------

def _make_replay_analysis(
    *,
    consistency_status: str = "consistent",
    trace_id: str = "trace-bx-001",
    replay_result_id: str = "replay-bx-001",
    analysis_id: str | None = None,
    drift_type: str | None = None,
    reproducibility_score: float = 0.9,
) -> Dict[str, Any]:
    """Build a minimal valid replay_decision_analysis artifact."""
    import uuid as _uuid
    return {
        "analysis_id": analysis_id or str(_uuid.uuid4()),
        "trace_id": trace_id,
        "replay_result_id": replay_result_id,
        "original_decision": {
            "decision_status": "allow",
            "decision_reason_code": "slo_pass",
        },
        "replay_decision": {
            "decision_status": "allow",
            "decision_reason_code": "slo_pass",
        },
        "decision_consistency": {
            "status": consistency_status,
            "differences": [],
        },
        "drift_type": drift_type,
        "reproducibility_score": reproducibility_score,
        "explanation": "Test artifact.",
        "created_at": "2025-01-01T00:00:00Z",
    }


# 22. Consistent replay → replay_consistency_sli = 1.0, no alert escalation
def test_bx_consistent_replay_sli():
    run_result = _make_run_result()
    replay_analysis = _make_replay_analysis(consistency_status="consistent")
    record = build_monitor_record(run_result, replay_analysis)

    assert record["sli_snapshot"]["replay_status"] == "consistent"
    assert record["sli_snapshot"]["replay_consistency_sli"] == pytest.approx(1.0)
    # Healthy run + consistent replay → no alert
    assert record["alert_recommendation"]["level"] == "none"


# 23. Drifted replay → replay_consistency_sli = 0.0, alert triggered
def test_bx_drifted_replay_triggers_alert():
    run_result = _make_run_result(overall_status="pass")
    replay_analysis = _make_replay_analysis(
        consistency_status="drifted",
        reproducibility_score=0.0,
    )
    record = build_monitor_record(run_result, replay_analysis)

    assert record["sli_snapshot"]["replay_status"] == "drifted"
    assert record["sli_snapshot"]["replay_consistency_sli"] == pytest.approx(0.0)
    # Drifted replay must escalate alert to at least warning
    assert record["alert_recommendation"]["level"] in ("warning", "critical")
    assert any(
        "drifted" in r for r in record["alert_recommendation"]["reasons"]
    )


# 24. Indeterminate replay → replay_consistency_sli ≤ 0.5, alert triggered
def test_bx_indeterminate_replay_triggers_alert():
    run_result = _make_run_result(overall_status="pass")
    replay_analysis = _make_replay_analysis(
        consistency_status="indeterminate",
        reproducibility_score=0.5,
    )
    record = build_monitor_record(run_result, replay_analysis)

    assert record["sli_snapshot"]["replay_status"] == "indeterminate"
    assert record["sli_snapshot"]["replay_consistency_sli"] <= 0.5
    # Indeterminate replay must escalate alert to at least warning
    assert record["alert_recommendation"]["level"] in ("warning", "critical")
    assert any(
        "indeterminate" in r for r in record["alert_recommendation"]["reasons"]
    )


# 25. Missing replay when require_replay=True → raises EvaluationMonitorError
def test_bx_missing_replay_when_required_raises():
    run_result = _make_run_result()
    with pytest.raises(EvaluationMonitorError, match="required but was not provided"):
        build_monitor_record(run_result, replay_decision_analysis=None, require_replay=True)


# 26. Invalid replay schema → raises InvalidReplayAnalysisError
def test_bx_invalid_replay_schema_raises():
    run_result = _make_run_result()
    # An artifact missing required fields is invalid
    bad_replay = {"not": "a valid replay_decision_analysis"}
    with pytest.raises(InvalidReplayAnalysisError):
        build_monitor_record(run_result, bad_replay)


# 27. Summary with replay records includes aggregates and trend
def test_bx_summary_replay_aggregates():
    run_result_1 = _make_run_result(run_id="r1")
    run_result_2 = _make_run_result(run_id="r2")
    replay_consistent = _make_replay_analysis(consistency_status="consistent")
    replay_drifted = _make_replay_analysis(
        consistency_status="drifted", reproducibility_score=0.0
    )
    records = [
        build_monitor_record(run_result_1, replay_consistent),
        build_monitor_record(run_result_2, replay_drifted),
    ]
    summary = summarize_monitor_records(records)

    # Average of 1.0 and 0.0 = 0.5
    assert "average_replay_consistency_sli" in summary["aggregates"]
    assert summary["aggregates"]["average_replay_consistency_sli"] == pytest.approx(0.5)
    assert "replay_consistency_trend" in summary["trend_analysis"]
    # Schema must still be valid
    errors = validate_monitor_summary(summary)
    assert errors == [], f"Schema errors: {errors}"


# 28. Records without replay still produce a schema-valid summary
def test_bx_summary_without_replay_schema_valid():
    records = [
        build_monitor_record(_load_json(_HEALTHY_1)),
        build_monitor_record(_load_json(_HEALTHY_2)),
    ]
    summary = summarize_monitor_records(records)
    assert "average_replay_consistency_sli" not in summary["aggregates"]
    assert "replay_consistency_trend" not in summary["trend_analysis"]
    errors = validate_monitor_summary(summary)
    assert errors == [], f"Schema errors: {errors}"
