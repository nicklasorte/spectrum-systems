"""Tests for rfx_repair_prompt_generator (RFX-N18)."""

from spectrum_systems.modules.runtime.rfx_repair_prompt_generator import (
    generate_rfx_repair_prompt,
    _ALWAYS_CONSTRAINTS,
)


def _proof(**kw):
    base = {
        "proof_ref": "proof-001",
        "root_cause": "Missing jsonschema import in dependency graph.",
        "owner_context": "PQX (execution) + EVL (eval coverage) — see system_registry.md",
        "validation_cmds": ["pytest tests/test_rfx_*.py -q", "python scripts/run_rfx_super_check.py"],
        "guard_constraints": ["Do not expand import surface beyond diagnosed path."],
    }
    base.update(kw)
    return base


# RT-N18: repair prompt lacking root cause → must fail.
def test_rt_n18_missing_root_cause_fails():
    result = generate_rfx_repair_prompt(rfx_proof=_proof(root_cause=""))
    assert "rfx_repair_missing_root_cause" in result["reason_codes_emitted"]
    assert result["status"] == "incomplete"


# RT-N18: missing owner context → must fail.
def test_rt_n18_missing_owner_context_fails():
    result = generate_rfx_repair_prompt(rfx_proof=_proof(owner_context=""))
    assert "rfx_repair_missing_owner_context" in result["reason_codes_emitted"]


# RT-N18: missing validation commands → must fail.
def test_rt_n18_missing_validation_cmds_fails():
    result = generate_rfx_repair_prompt(rfx_proof=_proof(validation_cmds=[]))
    assert "rfx_repair_missing_validation_cmds" in result["reason_codes_emitted"]


# RT-N18: missing guard constraints → must fail.
def test_rt_n18_missing_guard_constraints_fails():
    result = generate_rfx_repair_prompt(rfx_proof=_proof(guard_constraints=[]))
    assert "rfx_repair_missing_guard_constraints" in result["reason_codes_emitted"]


def test_empty_proof_guard_constraints_not_shared():
    # P2 fix: mutating the returned guard_constraints must not affect defaults.
    r1 = generate_rfx_repair_prompt(rfx_proof=None)
    r1["guard_constraints"].append("injected")
    r2 = generate_rfx_repair_prompt(rfx_proof=None)
    assert "injected" not in r2["guard_constraints"]


def test_rt_n18_complete_proof_passes():
    result = generate_rfx_repair_prompt(rfx_proof=_proof())
    assert result["status"] == "complete"
    assert result["reason_codes_emitted"] == []


def test_always_constraints_present():
    result = generate_rfx_repair_prompt(rfx_proof=_proof())
    for constraint in _ALWAYS_CONSTRAINTS:
        assert constraint in result["guard_constraints"]


def test_empty_proof_fails():
    result = generate_rfx_repair_prompt(rfx_proof=None)
    assert "rfx_repair_empty_proof" in result["reason_codes_emitted"]


def test_prompt_id_stable():
    r1 = generate_rfx_repair_prompt(rfx_proof=_proof())
    r2 = generate_rfx_repair_prompt(rfx_proof=_proof())
    assert r1["prompt_id"] == r2["prompt_id"]
    assert r1["prompt_id"] is not None


def test_completeness_score_full():
    result = generate_rfx_repair_prompt(rfx_proof=_proof())
    assert result["signals"]["completeness_score"] == 1.0


def test_extra_constraints_merged():
    result = generate_rfx_repair_prompt(
        rfx_proof=_proof(),
        extra_constraints=["Run authority shape check after fix."],
    )
    assert "Run authority shape check after fix." in result["guard_constraints"]


def test_artifact_type():
    result = generate_rfx_repair_prompt(rfx_proof=_proof())
    assert result["artifact_type"] == "rfx_repair_prompt"


def test_non_list_guard_constraints_does_not_raise():
    # P1 fix: non-list guard_constraints (e.g. a string) must not raise TypeError;
    # it should be treated as absent and trigger rfx_repair_missing_guard_constraints.
    result = generate_rfx_repair_prompt(
        rfx_proof=_proof(guard_constraints="not-a-list")
    )
    assert "rfx_repair_missing_guard_constraints" in result["reason_codes_emitted"]
    assert result["status"] == "incomplete"


def test_non_list_extra_constraints_does_not_raise():
    # P1 fix: non-list extra_constraints must not raise TypeError.
    result = generate_rfx_repair_prompt(
        rfx_proof=_proof(),
        extra_constraints="not-a-list",
    )
    assert result["artifact_type"] == "rfx_repair_prompt"


def test_string_validation_cmds_treated_as_missing():
    # P2 fix: a string validation_cmds must not pass the list check.
    result = generate_rfx_repair_prompt(
        rfx_proof=_proof(validation_cmds="pytest -q")
    )
    assert "rfx_repair_missing_validation_cmds" in result["reason_codes_emitted"]
    assert isinstance(result["validation_cmds"], list)


def test_list_validation_cmds_accepted():
    result = generate_rfx_repair_prompt(rfx_proof=_proof())
    assert isinstance(result["validation_cmds"], list)
    assert len(result["validation_cmds"]) > 0


def test_numeric_proof_ref_does_not_raise():
    # P1 fix: numeric proof_ref from JSON payloads must not raise AttributeError.
    result = generate_rfx_repair_prompt(rfx_proof=_proof(proof_ref=99))
    assert result["artifact_type"] == "rfx_repair_prompt"
    assert result["proof_ref"] == "99"


def test_numeric_root_cause_does_not_raise():
    # P1 fix: numeric root_cause must not raise AttributeError.
    result = generate_rfx_repair_prompt(rfx_proof=_proof(root_cause=0))
    assert "rfx_repair_missing_root_cause" in result["reason_codes_emitted"]


def test_missing_proof_ref_lowers_completeness_score():
    # P2 fix: missing proof_ref must reduce completeness_score below 1.0.
    result = generate_rfx_repair_prompt(rfx_proof=_proof(proof_ref=""))
    assert result["status"] == "incomplete"
    assert result["signals"]["completeness_score"] < 1.0


def test_missing_proof_ref_not_complete():
    # P2 fix: rfx_repair_missing_proof_ref alone must keep status incomplete.
    result = generate_rfx_repair_prompt(rfx_proof={
        "root_cause": "schema drift",
        "owner_context": "PQX",
        "validation_cmds": ["pytest -q"],
        "guard_constraints": ["no scope expansion"],
    })
    assert "rfx_repair_missing_proof_ref" in result["reason_codes_emitted"]
    assert result["status"] == "incomplete"
    assert result["signals"]["completeness_score"] < 1.0
