"""CL-01 / CL-02 / CL-03: core loop contract + handoff red team + fix pass."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.governance.core_loop_contract import (
    CANONICAL_REASON_PRECEDENCE,
    CANONICAL_STAGE_ORDER,
    CANONICAL_TRANSITIONS,
    CoreLoopContractError,
    REASON_CONTRACT_BAD_PRECEDENCE,
    REASON_CONTRACT_BAD_STAGE_ORDER,
    REASON_CONTRACT_BAD_TERMINAL,
    REASON_CONTRACT_BAD_TRANSITIONS,
    REASON_CONTRACT_MISSING_FIELD,
    REASON_HANDOFF_MISSING_FIELD,
    REASON_HANDOFF_MISSING_REF,
    REASON_HANDOFF_OUT_OF_ORDER,
    build_default_core_loop_contract,
    validate_core_loop_contract,
    validate_handoff,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PATH = REPO_ROOT / "contracts" / "examples" / "core_loop_contract.json"
SCHEMA_PATH = REPO_ROOT / "contracts" / "schemas" / "core_loop_contract.schema.json"


def _passing_handoff(from_stage: str, to_stage: str):
    return dict(
        handoff_fields={
            "trace_id": "t1",
            "run_id": "r1",
            "admission_class": "repo_mutation",
            "execution_status": "ok",
            "eval_summary_status": "ok",
            "policy_result_status": "allow",
            "control_outcome": "allow",
        },
        input_refs={
            "aex_admission_ref": "adm-1",
            "pqx_execution_envelope_ref": "env-1",
            "evl_eval_summary_ref": "evs-1",
            "tpa_policy_input_ref": "tpi-1",
            "tpa_policy_result_ref": "tpr-1",
            "cde_decision_input_ref": "cdi-1",
        },
        output_refs={
            "aex_admission_ref": "adm-1",
            "pqx_execution_envelope_ref": "env-1",
            "evl_eval_summary_ref": "evs-1",
            "tpa_policy_result_ref": "tpr-1",
            "cde_decision_ref": "cde-1",
        },
    )


# --- CL-01 ----------------------------------------------------------------


def test_cl01_default_contract_validates() -> None:
    c = build_default_core_loop_contract()
    result = validate_core_loop_contract(c)
    assert result["ok"], result["violations"]
    assert result["primary_reason"] == "CORE_LOOP_CONTRACT_OK"


def test_cl01_example_artifact_matches_canonical_shape() -> None:
    c = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    result = validate_core_loop_contract(c)
    assert result["ok"], result["violations"]
    assert c["stage_order"] == list(CANONICAL_STAGE_ORDER)
    assert c["reason_precedence"] == list(CANONICAL_REASON_PRECEDENCE)


def test_cl01_schema_file_lists_canonical_stages() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    enum = schema["properties"]["stage_order"]["items"]["enum"]
    assert enum == list(CANONICAL_STAGE_ORDER)


def test_cl01_validate_rejects_non_mapping_input() -> None:
    with pytest.raises(CoreLoopContractError):
        validate_core_loop_contract(["not", "a", "mapping"])  # type: ignore[arg-type]


# --- CL-02 (red team: malformed contract) ---------------------------------


def test_cl02_rejects_wrong_stage_order() -> None:
    c = build_default_core_loop_contract()
    c["stage_order"] = ["AEX", "PQX", "EVL", "CDE", "TPA", "SEL"]
    r = validate_core_loop_contract(c)
    assert not r["ok"]
    assert r["primary_reason"] == REASON_CONTRACT_BAD_STAGE_ORDER


def test_cl02_rejects_missing_terminal_status() -> None:
    c = build_default_core_loop_contract()
    c["terminal_statuses"] = ["pass", "block"]
    r = validate_core_loop_contract(c)
    assert not r["ok"]
    assert any(v["reason_code"] == REASON_CONTRACT_BAD_TERMINAL for v in r["violations"])


def test_cl02_rejects_wrong_transition_count() -> None:
    c = build_default_core_loop_contract()
    c["transitions"] = c["transitions"][:4]
    r = validate_core_loop_contract(c)
    assert not r["ok"]
    assert any(v["reason_code"] == REASON_CONTRACT_BAD_TRANSITIONS for v in r["violations"])


def test_cl02_rejects_wrong_precedence() -> None:
    c = build_default_core_loop_contract()
    c["reason_precedence"] = ["execution", "admission", "eval", "policy", "decision", "action"]
    r = validate_core_loop_contract(c)
    assert not r["ok"]
    assert any(v["reason_code"] == REASON_CONTRACT_BAD_PRECEDENCE for v in r["violations"])


def test_cl02_rejects_missing_required_field() -> None:
    c = build_default_core_loop_contract()
    c.pop("non_authority_assertions")
    r = validate_core_loop_contract(c)
    assert not r["ok"]
    assert any(v["reason_code"] == REASON_CONTRACT_MISSING_FIELD for v in r["violations"])


# --- CL-02 (red team: corrupted handoffs at every transition) ------------


@pytest.mark.parametrize("from_stage,to_stage", list(CANONICAL_TRANSITIONS))
def test_cl02_handoff_missing_field_blocks_transition(from_stage: str, to_stage: str) -> None:
    c = build_default_core_loop_contract()
    payload = _passing_handoff(from_stage, to_stage)
    payload["handoff_fields"] = {
        k: v for k, v in payload["handoff_fields"].items() if k != "trace_id"
    }
    result = validate_handoff(c, from_stage=from_stage, to_stage=to_stage, **payload)
    # AEX→PQX requires trace_id directly, others all require trace_id too.
    assert not result["ok"], (from_stage, to_stage)
    assert any(
        v["reason_code"] == REASON_HANDOFF_MISSING_FIELD for v in result["violations"]
    )


@pytest.mark.parametrize("from_stage,to_stage", list(CANONICAL_TRANSITIONS))
def test_cl02_handoff_missing_ref_blocks_transition(from_stage: str, to_stage: str) -> None:
    c = build_default_core_loop_contract()
    payload = _passing_handoff(from_stage, to_stage)
    # Wipe all input refs — at least one is required for every transition.
    payload["input_refs"] = {}
    result = validate_handoff(c, from_stage=from_stage, to_stage=to_stage, **payload)
    assert not result["ok"]
    assert any(
        v["reason_code"] == REASON_HANDOFF_MISSING_REF for v in result["violations"]
    )


def test_cl02_unknown_transition_fails_closed() -> None:
    c = build_default_core_loop_contract()
    payload = _passing_handoff("AEX", "PQX")
    result = validate_handoff(c, from_stage="AEX", to_stage="CDE", **payload)
    assert not result["ok"]
    assert result["primary_reason"] == REASON_HANDOFF_OUT_OF_ORDER


# --- CL-03 fix pass: passing handoffs validate ---------------------------


@pytest.mark.parametrize("from_stage,to_stage", list(CANONICAL_TRANSITIONS))
def test_cl03_passing_handoff_validates(from_stage: str, to_stage: str) -> None:
    c = build_default_core_loop_contract()
    payload = _passing_handoff(from_stage, to_stage)
    result = validate_handoff(c, from_stage=from_stage, to_stage=to_stage, **payload)
    assert result["ok"], result["violations"]
    assert result["primary_reason"] == "CORE_LOOP_HANDOFF_OK"
