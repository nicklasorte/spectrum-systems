"""CL-16 / CL-17 / CL-18: CDE decision-input contract, decision overreach red team, fix pass."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.governance.core_loop_decision_input_contract import (
    DecisionInputContractError,
    REASON_DASHBOARD,
    REASON_FREEZE_REQUIRED,
    REASON_FREE_TEXT,
    REASON_MISSING_EVAL,
    REASON_MISSING_EXECUTION,
    REASON_MISSING_TPA,
    REASON_OK,
    REASON_RUNBOOK,
    REASON_STALE,
    load_decision_input_contract,
    validate_decision_inputs,
    validate_decision_outcome,
)


def _passing_inputs():
    return {
        "aex_admission_result_ref": "adm-1",
        "pqx_execution_envelope_ref": "env-1",
        "evl_eval_summary_ref": "evs-1",
        "tpa_policy_result_ref": "tpr-1",
        "trace_id": "t1",
    }


# --- CL-16 contract loads ------------------------------------------------


def test_cl16_contract_loads_and_lists_required_keys() -> None:
    c = load_decision_input_contract()
    assert "tpa_policy_result_ref" in c["required_input_keys"]
    assert "evl_eval_summary_ref" in c["required_input_keys"]


def test_cl16_passing_inputs_validate() -> None:
    result = validate_decision_inputs(_passing_inputs())
    assert result["ok"], result["violations"]
    assert result["primary_reason"] == REASON_OK


def test_cl16_rejects_non_mapping() -> None:
    with pytest.raises(DecisionInputContractError):
        validate_decision_inputs("not a mapping")  # type: ignore[arg-type]


# --- CL-17 red team: overreach -------------------------------------------


def test_cl17_free_text_only_blocks() -> None:
    inputs = _passing_inputs()
    inputs["free_text_rationale"] = "ship it"
    result = validate_decision_inputs(inputs)
    assert not result["ok"]
    assert result["primary_reason"] == REASON_FREE_TEXT


def test_cl17_dashboard_only_blocks() -> None:
    inputs = _passing_inputs()
    inputs["dashboard_only_status"] = "green"
    result = validate_decision_inputs(inputs)
    assert not result["ok"]
    assert result["primary_reason"] == REASON_DASHBOARD


def test_cl17_runbook_only_blocks() -> None:
    inputs = _passing_inputs()
    inputs["operator_runbook_text"] = "do this"
    result = validate_decision_inputs(inputs)
    assert not result["ok"]
    assert result["primary_reason"] == REASON_RUNBOOK


def test_cl17_stale_proof_blocks() -> None:
    inputs = _passing_inputs()
    result = validate_decision_inputs(inputs, proof_age_seconds=10**9)
    assert not result["ok"]
    assert result["primary_reason"] == REASON_STALE


def test_cl17_missing_tpa_result_blocks_with_priority() -> None:
    inputs = _passing_inputs()
    inputs.pop("tpa_policy_result_ref")
    result = validate_decision_inputs(inputs)
    assert not result["ok"]
    assert result["primary_reason"] == REASON_MISSING_TPA


def test_cl17_missing_eval_summary_blocks() -> None:
    inputs = _passing_inputs()
    inputs.pop("evl_eval_summary_ref")
    result = validate_decision_inputs(inputs)
    assert not result["ok"]
    assert result["primary_reason"] == REASON_MISSING_EVAL


def test_cl17_missing_execution_envelope_blocks() -> None:
    inputs = _passing_inputs()
    inputs.pop("pqx_execution_envelope_ref")
    result = validate_decision_inputs(inputs)
    assert not result["ok"]
    assert result["primary_reason"] == REASON_MISSING_EXECUTION


# --- CL-18 fix pass ------------------------------------------------------


def test_cl18_decision_outcome_allow_validates() -> None:
    result = validate_decision_outcome({"decision": "allow", "cde_decision_ref": "cde-1"})
    assert result["ok"]
    assert result["primary_reason"] == REASON_OK


@pytest.mark.parametrize("decision", ["allow", "block", "freeze", "repair_required"])
def test_cl18_recognized_decisions_validate(decision: str) -> None:
    assert validate_decision_outcome({"decision": decision})["ok"]


def test_cl18_unknown_decision_freeze_required() -> None:
    result = validate_decision_outcome({"decision": "ship_it"})
    assert not result["ok"]
    assert result["primary_reason"] == REASON_FREEZE_REQUIRED


def test_cl18_missing_decision_freeze_required() -> None:
    result = validate_decision_outcome(None)
    assert not result["ok"]
    assert result["primary_reason"] == REASON_FREEZE_REQUIRED
