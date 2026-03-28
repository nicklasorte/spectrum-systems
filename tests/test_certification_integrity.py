"""Tests for VAL-11 certification integrity validation over real DONE-01 seam."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict

import pytest

from spectrum_systems.modules.governance.certification_integrity import (
    CertificationIntegrityError,
    run_certification_integrity_validation,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_EXAMPLES = _REPO_ROOT / "contracts" / "examples"


def _load_example(name: str) -> Dict[str, Any]:
    return json.loads((_EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


def _regression_result_pass(trace_id: str) -> Dict[str, Any]:
    return {
        "blocked": False,
        "regression_status": "pass",
        "schema_version": "1.1.0",
        "artifact_type": "regression_result",
        "run_id": "reg-run-001",
        "suite_id": "suite-001",
        "created_at": "2026-03-28T00:00:00Z",
        "total_traces": 1,
        "passed_traces": 1,
        "failed_traces": 0,
        "pass_rate": 1.0,
        "overall_status": "pass",
        "results": [
            {
                "trace_id": trace_id,
                "replay_result_id": "replay-001",
                "analysis_id": "analysis-001",
                "decision_status": "consistent",
                "reproducibility_score": 1.0,
                "drift_type": "",
                "passed": True,
                "failure_reasons": [],
                "baseline_replay_result_id": "base-001",
                "current_replay_result_id": "cur-001",
                "baseline_trace_id": trace_id,
                "current_trace_id": trace_id,
                "baseline_reference": "replay_result:base-001",
                "current_reference": "replay_result:cur-001",
                "mismatch_summary": [],
                "comparison_digest": "a" * 64,
            }
        ],
        "summary": {"drift_counts": {}, "average_reproducibility_score": 1.0},
    }


def _valid_input_refs() -> Dict[str, Any]:
    replay = _load_example("replay_result")
    replay["consistency_status"] = "match"
    replay["drift_detected"] = False
    replay["failure_reason"] = None

    trace_id = replay["trace_id"]
    replay["provenance"]["trace_id"] = trace_id
    replay["observability_metrics"]["trace_refs"]["trace_id"] = trace_id
    replay["error_budget_status"]["trace_refs"]["trace_id"] = trace_id

    budget = _load_example("error_budget_status")
    budget["budget_status"] = "healthy"
    budget["trace_refs"]["trace_id"] = trace_id

    control = _load_example("evaluation_control_decision")
    control["trace_id"] = trace_id
    control["decision"] = "allow"
    control["system_response"] = "allow"
    control["system_status"] = "healthy"

    failure = _load_example("governed_failure_injection_summary")
    failure["fail_count"] = 0
    failure["pass_count"] = failure["case_count"]
    for result in failure["results"]:
        result["passed"] = True
        result["expected_outcome"] = "block"
        result["observed_outcome"] = "block"
        result["invariant_violations"] = []

    return {
        "replay_results": [replay],
        "regression_results": [_regression_result_pass(trace_id)],
        "error_budget_statuses": [budget],
        "failure_injection_results": [failure],
        "control_decisions": [copy.deepcopy(control)],
        "policy_ref": copy.deepcopy(control),
    }


def _case_map(result: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {case["case_id"]: case for case in result["validation_cases"]}


def test_replay_regression_mismatch_blocks() -> None:
    result = run_certification_integrity_validation(_valid_input_refs())
    case = _case_map(result)["VAL11-A"]
    assert case["expected_outcome"] == "FAILED"
    assert case["actual_outcome"] == "FAILED"
    assert case["passed"] is True


def test_error_budget_exhaustion_blocks() -> None:
    result = run_certification_integrity_validation(_valid_input_refs())
    case = _case_map(result)["VAL11-B"]
    assert case["actual_outcome"] == "FAILED"
    assert case["passed"] is True


def test_failure_injection_violation_blocks() -> None:
    result = run_certification_integrity_validation(_valid_input_refs())
    case = _case_map(result)["VAL11-C"]
    assert case["actual_outcome"] == "FAILED"
    assert case["passed"] is True


def test_missing_input_fails_closed() -> None:
    result = run_certification_integrity_validation(_valid_input_refs())
    case = _case_map(result)["VAL11-E"]
    assert case["actual_outcome"] == "FAILED"
    assert case["passed"] is True


def test_trace_mismatch_blocks_or_is_flagged_false_certification() -> None:
    result = run_certification_integrity_validation(_valid_input_refs())
    case = _case_map(result)["VAL11-F"]
    if case["actual_outcome"] == "PASSED":
        assert result["summary"]["false_certification_detected"] is True
        assert result["final_status"] == "FAILED"
    else:
        assert case["actual_outcome"] == "FAILED"
        assert case["passed"] is True


def test_valid_case_passes() -> None:
    result = run_certification_integrity_validation(_valid_input_refs())
    case = _case_map(result)["VAL11-G"]
    assert case["actual_outcome"] == "PASSED"
    assert case["passed"] is True


def test_any_false_certification_causes_failed_final_status() -> None:
    result = run_certification_integrity_validation(_valid_input_refs())
    case = _case_map(result)["VAL11-F"]
    if case["actual_outcome"] == "PASSED":
        assert result["summary"]["false_certification_detected"] is True
        assert result["final_status"] == "FAILED"
    else:
        assert result["summary"]["false_certification_detected"] is False


def test_missing_input_array_rejected() -> None:
    with pytest.raises(CertificationIntegrityError, match="replay_results"):
        run_certification_integrity_validation({})
