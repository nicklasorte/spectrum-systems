"""Tests for VAL-10 policy enforcement integrity validation."""

from __future__ import annotations

from spectrum_systems.modules.governance.policy_enforcement_integrity import (
    run_policy_enforcement_integrity_validation,
)


def _case(result: dict, case_type: str) -> dict:
    for case in result["validation_cases"]:
        if case["case_type"] == case_type:
            return case
    raise AssertionError(f"missing case_type={case_type}")


def test_missing_policy_fails_closed() -> None:
    result = run_policy_enforcement_integrity_validation({})
    case = _case(result, "missing_policy_input")
    assert case["actual_outcome"] == "policy_resolution_error"
    assert case["bypass_detected"] is False
    assert case["passed"] is True


def test_malformed_policy_fails_closed() -> None:
    result = run_policy_enforcement_integrity_validation({})
    case = _case(result, "malformed_policy_input")
    assert case["actual_outcome"] == "registry_rejected"
    assert case["bypass_detected"] is False
    assert case["passed"] is True


def test_distinct_policies_produce_distinct_control_outcomes() -> None:
    result = run_policy_enforcement_integrity_validation({})
    case = _case(result, "control_seam_policy_enforcement")
    assert case["actual_outcome"].startswith("distinct:")
    assert case["bypass_detected"] is False
    assert case["passed"] is True


def test_restrictive_policy_cannot_be_bypassed_in_enforcement() -> None:
    result = run_policy_enforcement_integrity_validation({})
    case = _case(result, "enforcement_seam_policy_enforcement")
    assert case["actual_outcome"] in {"freeze", "block"}
    assert case["bypass_detected"] is False
    assert case["passed"] is True


def test_certification_does_not_false_pass_on_bad_policy_context() -> None:
    result = run_policy_enforcement_integrity_validation({})
    case = _case(result, "certification_seam_policy_enforcement")
    assert case["actual_outcome"] == "done_certification_error"
    assert case["bypass_detected"] is False
    assert case["passed"] is True


def test_backtesting_respects_actual_policy_identity() -> None:
    result = run_policy_enforcement_integrity_validation({})
    case = _case(result, "backtesting_policy_identity_integrity")
    assert case["actual_outcome"] == "distinct_policy_identities_honored"
    assert case["bypass_detected"] is False
    assert case["passed"] is True


def test_inconsistent_seam_application_causes_failed_final_status() -> None:
    result = run_policy_enforcement_integrity_validation({})
    case = _case(result, "inconsistent_policy_application")
    assert case["actual_outcome"] == "detected_inconsistent_policy_application"
    assert case["bypass_detected"] is True
    assert case["passed"] is True
    assert result["summary"]["inconsistent_policy_application_detected"] is True
    assert result["final_status"] == "FAILED"
