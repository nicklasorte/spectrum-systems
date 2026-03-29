from __future__ import annotations

import pytest

from spectrum_systems.modules.evaluation.eval_engine import run_eval_case


def _base_case() -> dict:
    return {
        "artifact_type": "eval_case",
        "schema_version": "1.0.0",
        "run_id": "run-eval-engine-test-001",
        "trace_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "eval_case_id": "eval-case-test-001",
        "input_artifact_refs": ["artifact://input/1"],
        "expected_output_spec": {"forced_status": "pass", "forced_score": 1.0},
        "scoring_rubric": {"pass_threshold": 0.8},
        "evaluation_type": "deterministic",
        "created_from": "manual",
    }


def test_run_eval_case_pass_case() -> None:
    case = _base_case()
    result = run_eval_case(case)
    assert result["result_status"] == "pass"
    assert result["score"] == 1.0
    assert result["eval_case_id"] == case["eval_case_id"]
    assert result["run_id"] == case["run_id"]
    assert result["trace_id"] == case["trace_id"]


def test_run_eval_case_fail_case() -> None:
    case = _base_case()
    case["expected_output_spec"]["forced_status"] = "fail"
    case["expected_output_spec"]["forced_score"] = 0.2
    result = run_eval_case(case)
    assert result["result_status"] == "fail"
    assert result["score"] == 0.2
    assert "expected_output_mismatch" in result["failure_modes"]


def test_run_eval_case_indeterminate_treated_as_failure() -> None:
    case = _base_case()

    def indeterminate_executor(_case: dict) -> dict:
        return {
            "result_status": "indeterminate",
            "score": 0.0,
            "failure_modes": [],
            "provenance_refs": [],
        }

    result = run_eval_case(case, executor=indeterminate_executor)
    assert result["result_status"] == "fail"
    assert "indeterminate_treated_as_failure" in result["failure_modes"]


def test_run_eval_case_requires_eval_case_id_and_trace_id() -> None:
    case = _base_case()
    case["trace_id"] = ""

    with pytest.raises(Exception):
        run_eval_case(case)
