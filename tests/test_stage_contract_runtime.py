from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema.exceptions import ValidationError

from spectrum_systems.modules.runtime.stage_contract_runtime import (
    evaluate_stage_transition_readiness,
    load_stage_contract,
    validate_stage_contract,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_PROMPT_QUEUE_CONTRACT_PATH = _REPO_ROOT / "contracts" / "examples" / "stage_contracts" / "prompt_queue_stage_contract.json"
_PQX_CONTRACT_PATH = _REPO_ROOT / "contracts" / "examples" / "stage_contracts" / "pqx_stage_contract.json"


def _pqx_contract() -> dict:
    return json.loads(_PQX_CONTRACT_PATH.read_text(encoding="utf-8"))


def test_stage_contract_schema_valid_fixture_passes() -> None:
    payload = json.loads(_PROMPT_QUEUE_CONTRACT_PATH.read_text(encoding="utf-8"))
    validate_stage_contract(payload)


def test_stage_contract_schema_unknown_field_fails() -> None:
    payload = _pqx_contract()
    payload["unknown_field"] = True
    with pytest.raises(ValidationError):
        validate_stage_contract(payload)


def test_stage_contract_loader_loads_valid_fixture() -> None:
    loaded = load_stage_contract(_PQX_CONTRACT_PATH)
    assert loaded["artifact_type"] == "stage_contract"
    assert loaded["stage"]["name"] == "promoted"


def test_stage_contract_loader_rejects_invalid_contract(tmp_path: Path) -> None:
    invalid = {"artifact_type": "stage_contract"}
    path = tmp_path / "invalid.stage_contract.json"
    path.write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_stage_contract(path)


def test_transition_readiness_all_required_signals_present_advances() -> None:
    result = evaluate_stage_transition_readiness(
        contract_payload=_pqx_contract(),
        present_input_artifacts={
            "replay_result": 1,
            "evaluation_control_decision": 1,
            "evaluation_enforcement_action": 1,
            "eval_coverage_summary": 1,
            "done_certification_record": 1,
        },
        present_output_artifacts={},
        eval_status_map={"certification_status": "pass", "promotion_control_allow": "pass"},
        trace_complete=True,
        policy_violation=False,
        budget_status={},
    )
    assert result.ready_to_advance is True
    assert result.recommended_state == "advance"
    assert result.reason_codes == ()


def test_transition_readiness_missing_input_blocks() -> None:
    result = evaluate_stage_transition_readiness(
        contract_payload=_pqx_contract(),
        present_input_artifacts={},
        present_output_artifacts={},
        eval_status_map={"certification_status": "pass", "promotion_control_allow": "pass"},
        trace_complete=True,
        policy_violation=False,
        budget_status={},
    )
    assert result.ready_to_advance is False
    assert result.recommended_state == "block"
    assert "STAGE_CONTRACT_REQUIRED_INPUT_MISSING" in result.reason_codes


def test_transition_readiness_missing_output_blocks_when_required() -> None:
    contract = _pqx_contract()
    contract["transition_rules"]["advance_requires_all_required_outputs"] = True
    result = evaluate_stage_transition_readiness(
        contract_payload=contract,
        present_input_artifacts={
            "replay_result": 1,
            "evaluation_control_decision": 1,
            "evaluation_enforcement_action": 1,
            "eval_coverage_summary": 1,
            "done_certification_record": 1,
        },
        present_output_artifacts={},
        eval_status_map={"certification_status": "pass", "promotion_control_allow": "pass"},
        trace_complete=True,
        policy_violation=False,
        budget_status={},
    )
    assert result.ready_to_advance is False
    assert "STAGE_CONTRACT_REQUIRED_OUTPUT_MISSING" in result.reason_codes


def test_transition_readiness_missing_eval_blocks() -> None:
    result = evaluate_stage_transition_readiness(
        contract_payload=_pqx_contract(),
        present_input_artifacts={
            "replay_result": 1,
            "evaluation_control_decision": 1,
            "evaluation_enforcement_action": 1,
            "eval_coverage_summary": 1,
            "done_certification_record": 1,
        },
        present_output_artifacts={},
        eval_status_map={"certification_status": "pass"},
        trace_complete=True,
        policy_violation=False,
        budget_status={},
    )
    assert result.ready_to_advance is False
    assert "STAGE_CONTRACT_MISSING_REQUIRED_EVAL" in result.reason_codes


def test_transition_readiness_failed_eval_blocks() -> None:
    result = evaluate_stage_transition_readiness(
        contract_payload=_pqx_contract(),
        present_input_artifacts={
            "replay_result": 1,
            "evaluation_control_decision": 1,
            "evaluation_enforcement_action": 1,
            "eval_coverage_summary": 1,
            "done_certification_record": 1,
        },
        present_output_artifacts={},
        eval_status_map={"certification_status": "fail", "promotion_control_allow": "pass"},
        trace_complete=True,
        policy_violation=False,
        budget_status={},
    )
    assert result.ready_to_advance is False
    assert "STAGE_CONTRACT_REQUIRED_EVAL_FAILED" in result.reason_codes


def test_transition_readiness_indeterminate_eval_with_freeze_behavior_freezes() -> None:
    contract = _pqx_contract()
    result = evaluate_stage_transition_readiness(
        contract_payload=contract,
        present_input_artifacts={
            "replay_result": 1,
            "evaluation_control_decision": 1,
            "evaluation_enforcement_action": 1,
            "eval_coverage_summary": 1,
            "done_certification_record": 1,
        },
        present_output_artifacts={},
        eval_status_map={"certification_status": "indeterminate", "promotion_control_allow": "pass"},
        trace_complete=True,
        policy_violation=False,
        budget_status={},
    )
    assert result.ready_to_advance is False
    assert "STAGE_CONTRACT_REQUIRED_EVAL_INDETERMINATE" in result.reason_codes
    assert result.recommended_state == "freeze"


def test_transition_readiness_trace_missing_blocks() -> None:
    result = evaluate_stage_transition_readiness(
        contract_payload=_pqx_contract(),
        present_input_artifacts={
            "replay_result": 1,
            "evaluation_control_decision": 1,
            "evaluation_enforcement_action": 1,
            "eval_coverage_summary": 1,
            "done_certification_record": 1,
        },
        present_output_artifacts={},
        eval_status_map={"certification_status": "pass", "promotion_control_allow": "pass"},
        trace_complete=False,
        policy_violation=False,
        budget_status={},
    )
    assert result.ready_to_advance is False
    assert result.recommended_state == "block"
    assert "STAGE_CONTRACT_TRACE_INCOMPLETE" in result.reason_codes


def test_transition_readiness_budget_exhausted_freezes_or_blocks_per_contract() -> None:
    contract = _pqx_contract()
    result_freeze = evaluate_stage_transition_readiness(
        contract_payload=contract,
        present_input_artifacts={
            "replay_result": 1,
            "evaluation_control_decision": 1,
            "evaluation_enforcement_action": 1,
            "eval_coverage_summary": 1,
            "done_certification_record": 1,
        },
        present_output_artifacts={},
        eval_status_map={"certification_status": "pass", "promotion_control_allow": "pass"},
        trace_complete=True,
        policy_violation=False,
        budget_status={"max_wall_clock_minutes": True},
    )
    assert result_freeze.ready_to_advance is False
    assert result_freeze.recommended_state == "freeze"

    contract["transition_rules"]["budget_exhausted_behavior"] = "block"
    result_block = evaluate_stage_transition_readiness(
        contract_payload=contract,
        present_input_artifacts={
            "replay_result": 1,
            "evaluation_control_decision": 1,
            "evaluation_enforcement_action": 1,
            "eval_coverage_summary": 1,
            "done_certification_record": 1,
        },
        present_output_artifacts={},
        eval_status_map={"certification_status": "pass", "promotion_control_allow": "pass"},
        trace_complete=True,
        policy_violation=False,
        budget_status={"max_wall_clock_minutes": True},
    )
    assert result_block.ready_to_advance is False
    assert result_block.recommended_state == "block"


def test_transition_readiness_same_inputs_are_deterministic() -> None:
    kwargs = {
        "contract_payload": _pqx_contract(),
        "present_input_artifacts": {
            "replay_result": 1,
            "evaluation_control_decision": 1,
            "evaluation_enforcement_action": 1,
            "eval_coverage_summary": 1,
            "done_certification_record": 1,
        },
        "present_output_artifacts": {},
        "eval_status_map": {"certification_status": "pass", "promotion_control_allow": "pass"},
        "trace_complete": True,
        "policy_violation": False,
        "budget_status": {},
    }
    first = evaluate_stage_transition_readiness(**kwargs).as_dict()
    second = evaluate_stage_transition_readiness(**kwargs).as_dict()
    assert first == second
