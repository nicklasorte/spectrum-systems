"""Tests for BR — Replay Regression Harness (regression_harness.py).

Covers:
 1.  valid suite load and validation
 2.  passing suite — all traces consistent and above score threshold
 3.  failing suite due to drift (status mismatch)
 4.  failing suite due to low reproducibility score
 5.  missing trace raises MissingTraceError
 6.  invalid suite schema raises InvalidSuiteError
 7.  CLI exit code: 0 on pass, 1 on fail, 2 on error
 8.  aggregate_regression_results summary correctness
 9.  evaluate_trace_pass_fail: both criteria fail simultaneously
10.  validate_regression_suite returns empty list for valid suite
11.  validate_regression_suite returns errors for invalid suite
12.  validate_regression_run_result returns empty list for valid result
13.  validate_regression_run_result returns errors for invalid result
14.  run_regression_suite calls run_replay_decision_analysis per trace
15.  run_regression_suite result is schema-validated before return
"""
from __future__ import annotations

import json
import sys
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from spectrum_systems.modules.runtime.regression_harness import (  # noqa: E402
    InvalidSuiteError,
    MissingTraceError,
    RegressionHarnessError,
    aggregate_regression_results,
    evaluate_trace_pass_fail,
    load_regression_suite,
    run_regression_suite,
    run_trace_regression,
    validate_regression_run_result,
    validate_regression_suite,
)
from spectrum_systems.modules.runtime.replay_decision_engine import (  # noqa: E402
    ReplayDecisionError,
    build_analysis_artifact,
)

# ---------------------------------------------------------------------------
# Schema paths
# ---------------------------------------------------------------------------

_SUITE_SCHEMA = _REPO_ROOT / "contracts" / "schemas" / "regression_suite_manifest.schema.json"
_RESULT_SCHEMA = _REPO_ROOT / "contracts" / "schemas" / "regression_run_result.schema.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _new_id() -> str:
    return str(uuid.uuid4())


def _make_suite(
    *,
    suite_id: str = "suite-test-001",
    suite_name: str = "Test Suite",
    version: str = "1.0.0",
    traces: List[Dict[str, Any]] | None = None,
    description: str = "Test suite description.",
) -> Dict[str, Any]:
    if traces is None:
        traces = [_make_trace_entry()]
    return {
        "suite_id": suite_id,
        "suite_name": suite_name,
        "version": version,
        "created_at": "2025-01-01T00:00:00Z",
        "description": description,
        "traces": traces,
    }


def _make_trace_entry(
    *,
    trace_id: str = "trace-001",
    expected_decision_status: str = "consistent",
    minimum_reproducibility_score: float = 0.8,
    tags: List[str] | None = None,
) -> Dict[str, Any]:
    return {
        "trace_id": trace_id,
        "expected_decision_status": expected_decision_status,
        "minimum_reproducibility_score": minimum_reproducibility_score,
        "tags": tags if tags is not None else ["test"],
    }


def _make_decision_summary(
    status: str = "allow",
    reason: str = "strict_valid_lineage",
    policy: str = "permissive",
    action: str = "proceed",
    ti: float = 1.0,
) -> Dict[str, Any]:
    return {
        "decision_status": status,
        "decision_reason_code": reason,
        "enforcement_policy": policy,
        "recommended_action": action,
        "traceability_integrity_sli": ti,
    }


def _make_analysis(
    trace_id: str = "trace-001",
    replay_result_id: str = "replay-001",
    consistency_status: str = "consistent",
    reproducibility_score: float = 1.0,
    drift_type: str | None = None,
) -> Dict[str, Any]:
    original = _make_decision_summary()
    replay_dec = _make_decision_summary()
    consistency = {"status": consistency_status, "differences": []}
    return build_analysis_artifact(
        trace_id=trace_id,
        replay_result_id=replay_result_id,
        original_decision=original,
        replay_decision=replay_dec,
        decision_consistency=consistency,
        drift_type=drift_type,
        reproducibility_score=reproducibility_score,
        explanation="Test explanation.",
    )


def _make_per_trace_result(
    *,
    trace_id: str = "trace-001",
    replay_result_id: str = "replay-001",
    analysis_id: str | None = None,
    decision_status: str = "consistent",
    reproducibility_score: float = 1.0,
    drift_type: str = "",
    passed: bool = True,
    failure_reasons: List[str] | None = None,
) -> Dict[str, Any]:
    return {
        "trace_id": trace_id,
        "replay_result_id": replay_result_id,
        "analysis_id": analysis_id or _new_id(),
        "decision_status": decision_status,
        "reproducibility_score": reproducibility_score,
        "drift_type": drift_type,
        "passed": passed,
        "failure_reasons": failure_reasons if failure_reasons is not None else [],
    }


# ---------------------------------------------------------------------------
# 1. Valid suite load and validation
# ---------------------------------------------------------------------------


def test_load_regression_suite_valid(tmp_path: Path) -> None:
    suite = _make_suite()
    suite_file = tmp_path / "suite.json"
    suite_file.write_text(json.dumps(suite), encoding="utf-8")

    loaded = load_regression_suite(suite_file)

    assert loaded["suite_id"] == "suite-test-001"
    assert loaded["suite_name"] == "Test Suite"
    assert len(loaded["traces"]) == 1


def test_load_regression_suite_file_not_found() -> None:
    with pytest.raises(InvalidSuiteError, match="not found"):
        load_regression_suite("/tmp/nonexistent-suite-99999.json")


def test_load_regression_suite_invalid_json(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(InvalidSuiteError, match="Failed to load"):
        load_regression_suite(bad_file)


# ---------------------------------------------------------------------------
# 2. validate_regression_suite
# ---------------------------------------------------------------------------


def test_validate_regression_suite_valid() -> None:
    suite = _make_suite()
    errors = validate_regression_suite(suite)
    assert errors == []


def test_validate_regression_suite_missing_suite_id() -> None:
    suite = _make_suite()
    del suite["suite_id"]
    errors = validate_regression_suite(suite)
    assert errors  # at least one error reported


def test_validate_regression_suite_empty_traces() -> None:
    suite = _make_suite(traces=[])
    errors = validate_regression_suite(suite)
    assert errors  # minItems=1 violated


def test_validate_regression_suite_invalid_score_range() -> None:
    trace = _make_trace_entry(minimum_reproducibility_score=1.5)
    suite = _make_suite(traces=[trace])
    errors = validate_regression_suite(suite)
    assert errors  # score > 1.0 violates schema


def test_validate_regression_suite_missing_trace_fields() -> None:
    suite = _make_suite(traces=[{"trace_id": "t1"}])  # missing required fields
    errors = validate_regression_suite(suite)
    assert errors


# ---------------------------------------------------------------------------
# 3. validate_regression_run_result
# ---------------------------------------------------------------------------


def test_validate_regression_run_result_valid() -> None:
    suite = _make_suite()
    per_trace = [_make_per_trace_result()]
    result = aggregate_regression_results(suite, per_trace)
    errors = validate_regression_run_result(result)
    assert errors == []


def test_validate_regression_run_result_missing_run_id() -> None:
    suite = _make_suite()
    per_trace = [_make_per_trace_result()]
    result = aggregate_regression_results(suite, per_trace)
    del result["run_id"]
    errors = validate_regression_run_result(result)
    assert errors


def test_validate_regression_run_result_invalid_overall_status() -> None:
    suite = _make_suite()
    per_trace = [_make_per_trace_result()]
    result = aggregate_regression_results(suite, per_trace)
    result["overall_status"] = "unknown"
    errors = validate_regression_run_result(result)
    assert errors


# ---------------------------------------------------------------------------
# 4. evaluate_trace_pass_fail
# ---------------------------------------------------------------------------


def test_evaluate_trace_pass_fail_passes() -> None:
    trace_entry = _make_trace_entry(
        trace_id="trace-abc",
        expected_decision_status="consistent",
        minimum_reproducibility_score=0.8,
    )
    analysis = _make_analysis(
        trace_id="trace-abc",
        consistency_status="consistent",
        reproducibility_score=1.0,
    )

    result = evaluate_trace_pass_fail(trace_entry, analysis)

    assert result["passed"] is True
    assert result["failure_reasons"] == []
    assert result["decision_status"] == "consistent"
    assert result["reproducibility_score"] == 1.0
    assert result["trace_id"] == "trace-abc"


def test_evaluate_trace_pass_fail_fails_on_drift() -> None:
    trace_entry = _make_trace_entry(
        expected_decision_status="consistent",
        minimum_reproducibility_score=0.0,
    )
    analysis = _make_analysis(
        consistency_status="drifted",
        reproducibility_score=0.0,
        drift_type="LOGIC_DRIFT",
    )

    result = evaluate_trace_pass_fail(trace_entry, analysis)

    assert result["passed"] is False
    assert any("drifted" in r for r in result["failure_reasons"])
    assert result["drift_type"] == "LOGIC_DRIFT"


def test_evaluate_trace_pass_fail_fails_on_low_score() -> None:
    trace_entry = _make_trace_entry(
        expected_decision_status="consistent",
        minimum_reproducibility_score=0.9,
    )
    analysis = _make_analysis(
        consistency_status="consistent",
        reproducibility_score=0.5,
    )

    result = evaluate_trace_pass_fail(trace_entry, analysis)

    assert result["passed"] is False
    assert any("reproducibility_score" in r for r in result["failure_reasons"])


def test_evaluate_trace_pass_fail_fails_both_criteria() -> None:
    trace_entry = _make_trace_entry(
        expected_decision_status="consistent",
        minimum_reproducibility_score=0.9,
    )
    analysis = _make_analysis(
        consistency_status="drifted",
        reproducibility_score=0.3,
        drift_type="INPUT_DRIFT",
    )

    result = evaluate_trace_pass_fail(trace_entry, analysis)

    assert result["passed"] is False
    assert len(result["failure_reasons"]) == 2


def test_evaluate_trace_pass_fail_drift_type_none_becomes_empty_string() -> None:
    trace_entry = _make_trace_entry(
        expected_decision_status="consistent",
        minimum_reproducibility_score=0.5,
    )
    analysis = _make_analysis(
        consistency_status="consistent",
        reproducibility_score=1.0,
        drift_type=None,
    )

    result = evaluate_trace_pass_fail(trace_entry, analysis)

    assert result["drift_type"] == ""
    assert result["passed"] is True


# ---------------------------------------------------------------------------
# 5. aggregate_regression_results
# ---------------------------------------------------------------------------


def test_aggregate_regression_results_all_pass() -> None:
    suite = _make_suite(suite_id="suite-agg-001")
    per_trace = [
        _make_per_trace_result(trace_id="t1", passed=True, reproducibility_score=1.0),
        _make_per_trace_result(trace_id="t2", passed=True, reproducibility_score=0.8),
    ]
    result = aggregate_regression_results(suite, per_trace)

    assert result["overall_status"] == "pass"
    assert result["total_traces"] == 2
    assert result["passed_traces"] == 2
    assert result["failed_traces"] == 0
    assert result["pass_rate"] == 1.0
    assert result["suite_id"] == "suite-agg-001"


def test_aggregate_regression_results_some_fail() -> None:
    suite = _make_suite(suite_id="suite-agg-002")
    per_trace = [
        _make_per_trace_result(trace_id="t1", passed=True, reproducibility_score=1.0),
        _make_per_trace_result(
            trace_id="t2",
            passed=False,
            reproducibility_score=0.2,
            drift_type="LOGIC_DRIFT",
            failure_reasons=["status mismatch"],
        ),
    ]
    result = aggregate_regression_results(suite, per_trace)

    assert result["overall_status"] == "fail"
    assert result["failed_traces"] == 1
    assert result["pass_rate"] == 0.5
    assert result["summary"]["drift_counts"].get("LOGIC_DRIFT", 0) == 1


def test_aggregate_regression_results_average_score() -> None:
    suite = _make_suite()
    per_trace = [
        _make_per_trace_result(reproducibility_score=0.6),
        _make_per_trace_result(reproducibility_score=1.0),
    ]
    result = aggregate_regression_results(suite, per_trace)

    assert abs(result["summary"]["average_reproducibility_score"] - 0.8) < 1e-9


def test_aggregate_regression_results_empty_traces() -> None:
    suite = _make_suite()
    result = aggregate_regression_results(suite, [])

    assert result["total_traces"] == 0
    assert result["overall_status"] == "pass"
    assert result["pass_rate"] == 0.0
    assert result["summary"]["average_reproducibility_score"] == 0.0


def test_aggregate_regression_results_drift_counts_multiple() -> None:
    suite = _make_suite()
    per_trace = [
        _make_per_trace_result(
            trace_id="t1", passed=False, drift_type="LOGIC_DRIFT",
            failure_reasons=["drift detected"]
        ),
        _make_per_trace_result(
            trace_id="t2", passed=False, drift_type="INPUT_DRIFT",
            failure_reasons=["drift detected"]
        ),
        _make_per_trace_result(
            trace_id="t3", passed=False, drift_type="LOGIC_DRIFT",
            failure_reasons=["drift detected"]
        ),
    ]
    result = aggregate_regression_results(suite, per_trace)

    dc = result["summary"]["drift_counts"]
    assert dc["LOGIC_DRIFT"] == 2
    assert dc["INPUT_DRIFT"] == 1


# ---------------------------------------------------------------------------
# 6. run_trace_regression — mocked
# ---------------------------------------------------------------------------


def test_run_trace_regression_success() -> None:
    trace_entry = _make_trace_entry(trace_id="trace-mock-001")
    analysis = _make_analysis(trace_id="trace-mock-001", consistency_status="consistent")

    with patch(
        "spectrum_systems.modules.runtime.regression_harness.run_replay_decision_analysis",
        return_value=analysis,
    ):
        result = run_trace_regression(trace_entry)

    assert result["trace_id"] == "trace-mock-001"
    assert result["decision_consistency"]["status"] == "consistent"


def test_run_trace_regression_missing_trace_raises() -> None:
    trace_entry = _make_trace_entry(trace_id="trace-missing-999")

    with patch(
        "spectrum_systems.modules.runtime.regression_harness.run_replay_decision_analysis",
        side_effect=ReplayDecisionError("trace not found"),
    ):
        with pytest.raises(MissingTraceError, match="trace not found"):
            run_trace_regression(trace_entry)


def test_run_trace_regression_unexpected_error_raises() -> None:
    trace_entry = _make_trace_entry(trace_id="trace-error-999")

    with patch(
        "spectrum_systems.modules.runtime.regression_harness.run_replay_decision_analysis",
        side_effect=RuntimeError("unexpected"),
    ):
        with pytest.raises(RegressionHarnessError, match="unexpected"):
            run_trace_regression(trace_entry)


# ---------------------------------------------------------------------------
# 7. run_regression_suite — end-to-end mocked
# ---------------------------------------------------------------------------


def _suite_file(tmp_path: Path, suite: Dict[str, Any]) -> Path:
    p = tmp_path / "suite.json"
    p.write_text(json.dumps(suite), encoding="utf-8")
    return p


def test_run_regression_suite_passing(tmp_path: Path) -> None:
    suite = _make_suite(traces=[_make_trace_entry(trace_id="trace-p1")])
    sf = _suite_file(tmp_path, suite)
    analysis = _make_analysis(
        trace_id="trace-p1",
        consistency_status="consistent",
        reproducibility_score=1.0,
    )

    with patch(
        "spectrum_systems.modules.runtime.regression_harness.run_replay_decision_analysis",
        return_value=analysis,
    ):
        result = run_regression_suite(sf)

    assert result["overall_status"] == "pass"
    assert result["passed_traces"] == 1
    assert result["failed_traces"] == 0
    errors = validate_regression_run_result(result)
    assert errors == []


def test_run_regression_suite_failing_due_to_drift(tmp_path: Path) -> None:
    suite = _make_suite(
        traces=[
            _make_trace_entry(
                trace_id="trace-drift-001",
                expected_decision_status="consistent",
                minimum_reproducibility_score=0.5,
            )
        ]
    )
    sf = _suite_file(tmp_path, suite)
    analysis = _make_analysis(
        trace_id="trace-drift-001",
        consistency_status="drifted",
        reproducibility_score=0.0,
        drift_type="LOGIC_DRIFT",
    )

    with patch(
        "spectrum_systems.modules.runtime.regression_harness.run_replay_decision_analysis",
        return_value=analysis,
    ):
        result = run_regression_suite(sf)

    assert result["overall_status"] == "fail"
    assert result["failed_traces"] == 1
    assert result["results"][0]["passed"] is False
    assert result["results"][0]["drift_type"] == "LOGIC_DRIFT"


def test_run_regression_suite_failing_due_to_low_score(tmp_path: Path) -> None:
    suite = _make_suite(
        traces=[
            _make_trace_entry(
                trace_id="trace-score-001",
                expected_decision_status="consistent",
                minimum_reproducibility_score=0.9,
            )
        ]
    )
    sf = _suite_file(tmp_path, suite)
    analysis = _make_analysis(
        trace_id="trace-score-001",
        consistency_status="consistent",
        reproducibility_score=0.4,
    )

    with patch(
        "spectrum_systems.modules.runtime.regression_harness.run_replay_decision_analysis",
        return_value=analysis,
    ):
        result = run_regression_suite(sf)

    assert result["overall_status"] == "fail"
    assert result["results"][0]["passed"] is False
    reasons = result["results"][0]["failure_reasons"]
    assert any("reproducibility_score" in r for r in reasons)


def test_run_regression_suite_missing_trace_raises(tmp_path: Path) -> None:
    suite = _make_suite(traces=[_make_trace_entry(trace_id="trace-gone")])
    sf = _suite_file(tmp_path, suite)

    with patch(
        "spectrum_systems.modules.runtime.regression_harness.run_replay_decision_analysis",
        side_effect=ReplayDecisionError("no such trace"),
    ):
        with pytest.raises(MissingTraceError):
            run_regression_suite(sf)


def test_run_regression_suite_invalid_suite_raises(tmp_path: Path) -> None:
    bad_suite = {"suite_id": "only-id"}  # missing required fields
    sf = _suite_file(tmp_path, bad_suite)

    with pytest.raises(InvalidSuiteError):
        run_regression_suite(sf)


def test_run_regression_suite_result_is_schema_valid(tmp_path: Path) -> None:
    traces = [
        _make_trace_entry(trace_id=f"trace-{i}", minimum_reproducibility_score=0.5)
        for i in range(3)
    ]
    suite = _make_suite(traces=traces)
    sf = _suite_file(tmp_path, suite)

    def mock_analysis(trace_id: str, **kwargs: Any) -> Dict[str, Any]:
        return _make_analysis(
            trace_id=trace_id,
            consistency_status="consistent",
            reproducibility_score=1.0,
        )

    with patch(
        "spectrum_systems.modules.runtime.regression_harness.run_replay_decision_analysis",
        side_effect=mock_analysis,
    ):
        result = run_regression_suite(sf)

    errors = validate_regression_run_result(result)
    assert errors == [], f"Schema errors: {errors}"


# ---------------------------------------------------------------------------
# 8. CLI exit codes
# ---------------------------------------------------------------------------


def test_cli_exit_code_pass(tmp_path: Path) -> None:
    from scripts.run_regression_suite import main

    suite = _make_suite(traces=[_make_trace_entry(trace_id="trace-cli-p")])
    sf = _suite_file(tmp_path, suite)
    analysis = _make_analysis(trace_id="trace-cli-p", consistency_status="consistent")

    with patch(
        "spectrum_systems.modules.runtime.regression_harness.run_replay_decision_analysis",
        return_value=analysis,
    ), patch("scripts.run_regression_suite._OUTPUT_DIR", tmp_path):
        code = main(["--suite", str(sf)])

    assert code == 0


def test_cli_exit_code_fail(tmp_path: Path) -> None:
    from scripts.run_regression_suite import main

    suite = _make_suite(
        traces=[
            _make_trace_entry(
                trace_id="trace-cli-f",
                expected_decision_status="consistent",
                minimum_reproducibility_score=0.9,
            )
        ]
    )
    sf = _suite_file(tmp_path, suite)
    analysis = _make_analysis(
        trace_id="trace-cli-f",
        consistency_status="drifted",
        reproducibility_score=0.0,
        drift_type="LOGIC_DRIFT",
    )

    with patch(
        "spectrum_systems.modules.runtime.regression_harness.run_replay_decision_analysis",
        return_value=analysis,
    ), patch("scripts.run_regression_suite._OUTPUT_DIR", tmp_path):
        code = main(["--suite", str(sf)])

    assert code == 1


def test_cli_exit_code_error_invalid_suite(tmp_path: Path) -> None:
    from scripts.run_regression_suite import main

    bad = tmp_path / "bad.json"
    bad.write_text('{"only": "this"}', encoding="utf-8")

    code = main(["--suite", str(bad)])
    assert code == 2


def test_cli_exit_code_error_missing_file() -> None:
    from scripts.run_regression_suite import main

    code = main(["--suite", "/tmp/no-such-file-regression-99.json"])
    assert code == 2


def test_cli_exit_code_error_missing_trace(tmp_path: Path) -> None:
    from scripts.run_regression_suite import main

    suite = _make_suite(traces=[_make_trace_entry(trace_id="trace-no-exist")])
    sf = _suite_file(tmp_path, suite)

    with patch(
        "spectrum_systems.modules.runtime.regression_harness.run_replay_decision_analysis",
        side_effect=ReplayDecisionError("not found"),
    ), patch("scripts.run_regression_suite._OUTPUT_DIR", tmp_path):
        code = main(["--suite", str(sf)])

    assert code == 2


# ---------------------------------------------------------------------------
# 9. Schema files exist
# ---------------------------------------------------------------------------


def test_regression_suite_manifest_schema_file_exists() -> None:
    assert _SUITE_SCHEMA.is_file(), f"Missing schema: {_SUITE_SCHEMA}"


def test_regression_run_result_schema_file_exists() -> None:
    assert _RESULT_SCHEMA.is_file(), f"Missing schema: {_RESULT_SCHEMA}"
