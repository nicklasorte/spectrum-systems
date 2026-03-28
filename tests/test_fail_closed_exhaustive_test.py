from __future__ import annotations

import copy

from spectrum_systems.modules.governance import fail_closed_exhaustive_test as val02


def _run() -> dict:
    return val02.run_fail_closed_exhaustive_test({"trace_id": "trace-val02-test"})


def _result_by_case(result: dict, case_id: str) -> dict:
    for case in result["seam_results"]:
        if case["case_id"] == case_id:
            return case
    raise AssertionError(f"missing case: {case_id}")


def test_replay_seam_failure_blocks() -> None:
    result = _run()
    assert _result_by_case(result, "replay_missing_input")["passed"] is True
    assert _result_by_case(result, "replay_malformed_artifact")["passed"] is True
    assert _result_by_case(result, "replay_inconsistent_comparison_fields")["passed"] is True


def test_eval_control_seam_failure_blocks() -> None:
    result = _run()
    assert _result_by_case(result, "eval_malformed_summary")["passed"] is True
    assert _result_by_case(result, "eval_missing_required_fields")["passed"] is True
    assert _result_by_case(result, "eval_ambiguous_indeterminate")["passed"] is True


def test_enforcement_seam_failure_blocks() -> None:
    result = _run()
    assert _result_by_case(result, "enforcement_invalid_input")["passed"] is True
    assert _result_by_case(result, "enforcement_missing_promotion_evidence")["passed"] is True
    assert _result_by_case(result, "enforcement_malformed_certification")["passed"] is True


def test_certification_seam_failure_blocks() -> None:
    result = _run()
    assert _result_by_case(result, "done_missing_required_refs")["passed"] is True
    assert _result_by_case(result, "done_invalid_error_budget_shape")["passed"] is True
    assert _result_by_case(result, "done_malformed_certification_pack")["passed"] is True
    assert _result_by_case(result, "done_inconsistent_check_results")["passed"] is True


def test_xrun_seam_failure_blocks() -> None:
    result = _run()
    assert _result_by_case(result, "xrun_insufficient_inputs")["passed"] is True
    assert _result_by_case(result, "xrun_malformed_trend_metrics")["passed"] is True
    assert _result_by_case(result, "xrun_inconsistent_pattern_payload")["passed"] is True


def test_policy_backtest_seam_failure_blocks() -> None:
    result = _run()
    assert _result_by_case(result, "policy_missing_baseline")["passed"] is True
    assert _result_by_case(result, "policy_malformed_candidate")["passed"] is True
    assert _result_by_case(result, "policy_inconsistent_decision_inputs")["passed"] is True


def test_any_silent_success_causes_failed_final_status(monkeypatch) -> None:
    original_cases = val02._cases()
    silent_case = {
        "seam_name": "synthetic",
        "case_id": "synthetic_silent_success",
        "case_type": "silent_success",
        "fn": lambda: {
            "actual_outcome": "allow",
            "failure_artifact_ref": "synthetic-ref",
            "blocking_reason": "unexpected allow",
            "is_blocking": False,
            "is_ambiguous": False,
        },
    }
    monkeypatch.setattr(val02, "_cases", lambda: copy.deepcopy(original_cases) + [silent_case])

    result = val02.run_fail_closed_exhaustive_test({})

    assert result["summary"]["silent_success_detected"] is True
    assert result["final_status"] == "FAILED"


def test_any_ambiguous_outcome_causes_failed_final_status(monkeypatch) -> None:
    original_cases = val02._cases()
    ambiguous_case = {
        "seam_name": "synthetic",
        "case_id": "synthetic_ambiguous",
        "case_type": "ambiguous",
        "fn": lambda: {
            "actual_outcome": "ambiguous",
            "failure_artifact_ref": "synthetic-ref",
            "blocking_reason": "ambiguous decision",
            "is_blocking": False,
            "is_ambiguous": True,
        },
    }
    monkeypatch.setattr(val02, "_cases", lambda: copy.deepcopy(original_cases) + [ambiguous_case])

    result = val02.run_fail_closed_exhaustive_test({})

    assert result["summary"]["ambiguous_outcome_detected"] is True
    assert result["final_status"] == "FAILED"
