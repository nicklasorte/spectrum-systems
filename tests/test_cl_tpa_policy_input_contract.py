"""CL-13 / CL-14 / CL-15: TPA policy-input contract, hidden input red team, fix pass."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.governance.core_loop_policy_input_contract import (
    PolicyInputContractError,
    REASON_DASHBOARD,
    REASON_HIDDEN,
    REASON_MISSING,
    REASON_NARRATIVE,
    REASON_OK,
    REASON_RESULT_MISSING,
    REASON_UNGOVERNED,
    load_policy_input_contract,
    validate_policy_inputs,
    validate_policy_result,
)


def _passing_inputs():
    return {
        "aex_admission_ref": "adm-1",
        "pqx_execution_envelope_ref": "env-1",
        "evl_eval_summary_ref": "evs-1",
        "trace_id": "t1",
    }


# --- CL-13 contract loads ------------------------------------------------


def test_cl13_contract_loads_and_lists_required_keys() -> None:
    c = load_policy_input_contract()
    assert "aex_admission_ref" in c["required_input_keys"]
    assert "trace_id" in c["required_input_keys"]


def test_cl13_passing_inputs_validate() -> None:
    result = validate_policy_inputs(_passing_inputs())
    assert result["ok"], result["violations"]
    assert result["primary_reason"] == REASON_OK


def test_cl13_validator_rejects_non_mapping() -> None:
    with pytest.raises(PolicyInputContractError):
        validate_policy_inputs("not a mapping")  # type: ignore[arg-type]


# --- CL-14 red team: hidden / dashboard / narrative ----------------------


def test_cl14_dashboard_only_blocks() -> None:
    inputs = _passing_inputs()
    inputs["dashboard_status"] = "green"
    result = validate_policy_inputs(inputs)
    assert not result["ok"]
    assert result["primary_reason"] == REASON_DASHBOARD


def test_cl14_narrative_only_blocks() -> None:
    inputs = _passing_inputs()
    inputs["narrative_rationale"] = "looks fine to me"
    result = validate_policy_inputs(inputs)
    assert not result["ok"]
    # Hidden has higher precedence than narrative; here only narrative is set.
    assert result["primary_reason"] == REASON_NARRATIVE


def test_cl14_hidden_state_blocks_with_higher_precedence() -> None:
    inputs = _passing_inputs()
    inputs["hidden_state"] = "secret"
    inputs["dashboard_status"] = "green"
    result = validate_policy_inputs(inputs)
    assert not result["ok"]
    # Hidden > dashboard
    assert result["primary_reason"] == REASON_HIDDEN
    # Supporting violation preserved
    assert any(v["reason_code"] == REASON_DASHBOARD for v in result["violations"])


def test_cl14_undocumented_input_blocks() -> None:
    inputs = _passing_inputs()
    inputs["arbitrary_undocumented_key"] = "whatever"
    result = validate_policy_inputs(inputs)
    assert not result["ok"]
    assert result["primary_reason"] == REASON_UNGOVERNED


def test_cl14_glob_dashboard_pattern_blocks() -> None:
    inputs = _passing_inputs()
    inputs["dashboard_truth_summary"] = "x"
    result = validate_policy_inputs(inputs)
    assert not result["ok"]


def test_cl14_missing_required_input_blocks() -> None:
    inputs = _passing_inputs()
    inputs.pop("evl_eval_summary_ref")
    result = validate_policy_inputs(inputs)
    assert not result["ok"]
    assert any(v["reason_code"] == REASON_MISSING for v in result["violations"])


# --- CL-15 fix pass ------------------------------------------------------


def test_cl15_passing_policy_result_validates() -> None:
    result = validate_policy_result(
        {
            "trace_id": "t1",
            "policy_result_status": "allow",
            "tpa_policy_result_ref": "tpr-1",
        }
    )
    assert result["ok"]
    assert result["primary_reason"] == REASON_OK


def test_cl15_missing_policy_result_blocks() -> None:
    result = validate_policy_result(None)
    assert not result["ok"]
    assert result["primary_reason"] == REASON_RESULT_MISSING


def test_cl15_invalid_policy_status_blocks() -> None:
    result = validate_policy_result(
        {
            "trace_id": "t1",
            "policy_result_status": "maybe",
            "tpa_policy_result_ref": "tpr-1",
        }
    )
    assert not result["ok"]
    assert result["primary_reason"] == REASON_RESULT_MISSING
