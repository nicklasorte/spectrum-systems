"""Tests for VAL-08 end-to-end failure simulation."""

from __future__ import annotations

from spectrum_systems.modules.governance.end_to_end_failure_simulation import (
    run_end_to_end_failure_simulation,
)


def _case_map(result: dict) -> dict:
    return {case["case_id"]: case for case in result["simulation_cases"]}


def test_malformed_context_blocks_end_to_end() -> None:
    result = run_end_to_end_failure_simulation({})
    case = _case_map(result)["VAL08-A"]
    assert case["blocked"] is True
    assert case["passed"] is True


def test_replay_mismatch_prevents_certification_promotion() -> None:
    result = run_end_to_end_failure_simulation({})
    case = _case_map(result)["VAL08-B"]
    assert case["blocked"] is True
    assert "done_certification_record:" in case["control_decision_ref"]


def test_control_inconsistency_blocks() -> None:
    result = run_end_to_end_failure_simulation({})
    case = _case_map(result)["VAL08-C"]
    assert case["blocked"] is True
    assert case["enforcement_action_ref"].startswith("evaluation_enforcement_action:")


def test_exhausted_budget_blocks() -> None:
    result = run_end_to_end_failure_simulation({})
    case = _case_map(result)["VAL08-D"]
    assert case["blocked"] is True


def test_failure_injection_violation_blocks() -> None:
    result = run_end_to_end_failure_simulation({})
    case = _case_map(result)["VAL08-E"]
    assert case["blocked"] is True


def test_multi_fault_blocks_with_explicit_artifacts() -> None:
    result = run_end_to_end_failure_simulation({})
    case = _case_map(result)["VAL08-G"]
    assert case["blocked"] is True
    assert len(case["failure_artifact_refs"]) > 0


def test_silent_propagation_forces_failed_final_status() -> None:
    result = run_end_to_end_failure_simulation({"inject_silent_propagation_for_testing": True})
    assert result["summary"]["silent_propagation_detected"] is True
    assert result["final_status"] == "FAILED"


def test_missing_failure_artifact_forces_failed_final_status() -> None:
    result = run_end_to_end_failure_simulation({"inject_missing_failure_artifact_for_testing": True})
    assert result["summary"]["missing_failure_artifact_detected"] is True
    assert result["final_status"] == "FAILED"


def test_end_to_end_regression_still_yields_nonempty_case_set() -> None:
    result = run_end_to_end_failure_simulation({})
    assert len(result["simulation_cases"]) >= 1
