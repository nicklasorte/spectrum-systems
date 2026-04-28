"""CL-26 / CL-27: Final red team — full loop drill across pass / block / freeze /
corrupted transitions / stale proof / conflicting proof / SEL action block."""

from __future__ import annotations

import copy

import pytest

from spectrum_systems.modules.governance.core_loop_decision_input_contract import (
    REASON_STALE,
    validate_decision_inputs,
)
from spectrum_systems.modules.governance.core_loop_proof import build_core_loop_proof


def _baseline():
    return dict(
        proof_id="clp-final",
        trace_id="t1",
        run_id="r1",
        audit_timestamp="2026-04-28T12:00:00Z",
        admission_packet={
            "admission_class": "repo_mutation",
            "trace_id": "t1",
            "run_id": "r1",
            "aex_admission_ref": "adm-1",
        },
        execution_envelope={
            "run_id": "r1",
            "trace_id": "t1",
            "input_refs": ["in-1"],
            "output_refs": ["env-1"],
            "output_hash": "sha256:abc",
            "status": "ok",
            "replay_ref": "rpl-1",
            "replayable": True,
            "aex_admission_ref": "adm-1",
        },
        eval_resolution_inputs={
            "declared_catalog": [{"name": "core", "required": True}],
            "submitted_evals": [{"name": "core", "required": True, "result": "pass"}],
        },
        eval_summary_ref="evs-1",
        policy_inputs={
            "aex_admission_ref": "adm-1",
            "pqx_execution_envelope_ref": "env-1",
            "evl_eval_summary_ref": "evs-1",
            "trace_id": "t1",
            "tpa_policy_input_ref": "tpi-1",
        },
        policy_result={
            "trace_id": "t1",
            "policy_result_status": "allow",
            "tpa_policy_result_ref": "tpr-1",
        },
        decision_inputs={
            "aex_admission_result_ref": "adm-1",
            "pqx_execution_envelope_ref": "env-1",
            "evl_eval_summary_ref": "evs-1",
            "tpa_policy_result_ref": "tpr-1",
            "trace_id": "t1",
            "cde_decision_input_ref": "cdi-1",
        },
        decision_outcome={"decision": "allow", "cde_decision_ref": "cde-1"},
        sel_action={"action": "allow_continuation", "sel_action_ref": "sel-1"},
        lineage_chain_ref="lin-1",
        replay_record_ref="rpl-1",
    )


# --- 1. clean pass -------------------------------------------------------


def test_cl26_clean_pass() -> None:
    proof = build_core_loop_proof(**_baseline())
    assert proof["terminal_status"] == "pass"
    assert proof["primary_reason"]["primary_canonical_reason"] == "CORE_LOOP_PASS"
    assert all(t["status"] == "ok" for t in proof["transitions"])


# --- 2. admission block --------------------------------------------------


def test_cl26_admission_block() -> None:
    kw = _baseline()
    kw["admission_packet"] = {"admission_class": "repo_mutation", "trace_id": "t1", "run_id": "r1"}
    proof = build_core_loop_proof(**kw)
    assert proof["terminal_status"] == "block"
    assert proof["primary_reason"]["source_stage"] == "AEX"
    assert proof["primary_reason"]["primary_canonical_reason"] == "ADMISSION_REPO_MUTATION_WITHOUT_PROOF"


# --- 3. execution block --------------------------------------------------


def test_cl26_execution_block() -> None:
    kw = _baseline()
    kw["execution_envelope"]["output_hash"] = ""
    proof = build_core_loop_proof(**kw)
    assert proof["terminal_status"] == "block"
    assert proof["primary_reason"]["source_stage"] == "PQX"
    assert proof["primary_reason"]["primary_canonical_reason"] == "EXECUTION_OUTPUT_HASH_MISSING"


# --- 4. eval block -------------------------------------------------------


def test_cl26_eval_block() -> None:
    kw = _baseline()
    kw["eval_resolution_inputs"]["submitted_evals"] = [
        {"name": "core", "required": True, "result": "fail"}
    ]
    proof = build_core_loop_proof(**kw)
    assert proof["terminal_status"] == "block"
    assert proof["primary_reason"]["source_stage"] == "EVL"


# --- 5. policy block -----------------------------------------------------


def test_cl26_policy_block() -> None:
    kw = _baseline()
    kw["policy_inputs"]["dashboard_status"] = "green"
    proof = build_core_loop_proof(**kw)
    assert proof["terminal_status"] == "block"
    assert proof["primary_reason"]["source_stage"] == "TPA"


# --- 6. decision freeze --------------------------------------------------


def test_cl26_decision_freeze() -> None:
    kw = _baseline()
    kw["decision_outcome"] = None
    proof = build_core_loop_proof(**kw)
    assert proof["terminal_status"] == "freeze"
    assert proof["primary_reason"]["source_stage"] == "CDE"


# --- 7. SEL action block -------------------------------------------------


def test_cl26_sel_action_block() -> None:
    kw = _baseline()
    kw["decision_outcome"] = {"decision": "block", "cde_decision_ref": "cde-blk"}
    kw["sel_action"] = {"action": "allow_continuation", "sel_action_ref": "sel-bad"}
    proof = build_core_loop_proof(**kw)
    assert proof["terminal_status"] == "block"
    primary = proof["primary_reason"]["primary_canonical_reason"]
    assert primary.startswith("ACTION_") or primary.startswith("DECISION_")


# --- 8. corrupted transition --------------------------------------------


def test_cl26_corrupted_transition_pqx_to_evl() -> None:
    kw = _baseline()
    # Corrupt the upstream stage so its required_output_ref isn't surfaced.
    kw["execution_envelope"]["output_refs"] = []
    proof = build_core_loop_proof(**kw)
    assert proof["terminal_status"] == "block"
    transition_statuses = {(t["from_stage"], t["to_stage"]): t["status"] for t in proof["transitions"]}
    assert transition_statuses[("PQX", "EVL")] == "failed"


# --- 9. stale proof ------------------------------------------------------


def test_cl26_stale_proof_via_decision_inputs() -> None:
    inputs = {
        "aex_admission_result_ref": "adm-1",
        "pqx_execution_envelope_ref": "env-1",
        "evl_eval_summary_ref": "evs-1",
        "tpa_policy_result_ref": "tpr-1",
        "trace_id": "t1",
    }
    result = validate_decision_inputs(inputs, proof_age_seconds=10**9)
    assert not result["ok"]
    assert result["primary_reason"] == REASON_STALE


# --- 10. conflicting proof (multiple simultaneous failures) ------------


def test_cl26_conflicting_proof_picks_admission_first() -> None:
    """When admission, execution, eval, policy, and decision all fail
    together, the primary reason must come from admission and supporting
    detail must preserve the rest. No silent fallback.
    """
    kw = _baseline()
    kw["admission_packet"] = {"admission_class": "repo_mutation"}  # missing trace, run, proof
    kw["execution_envelope"]["output_hash"] = ""
    kw["eval_resolution_inputs"]["submitted_evals"] = []
    kw["policy_inputs"]["dashboard_status"] = "green"
    kw["decision_outcome"] = None
    proof = build_core_loop_proof(**kw)
    assert proof["terminal_status"] in ("block", "freeze")
    assert proof["primary_reason"]["source_stage"] == "AEX"
    supporting_codes = {s["reason_code"] for s in proof["primary_reason"]["supporting_reasons"]}
    # Each failed stage must surface at least one supporting reason.
    assert any(c.startswith("EXECUTION_") for c in supporting_codes)
    assert any(c.startswith("EVAL_") for c in supporting_codes)
    assert any(c.startswith("POLICY_") for c in supporting_codes)
    assert any(c.startswith("DECISION_") for c in supporting_codes)


# --- 11. no silent fallback when sel_action contradicts decision -------


def test_cl26_no_unsupported_allow_when_decision_freeze_but_sel_pretends_allow() -> None:
    kw = _baseline()
    kw["decision_outcome"] = {"decision": "freeze", "cde_decision_ref": "cde-frz"}
    kw["sel_action"] = {"action": "allow_continuation", "sel_action_ref": "sel-bad"}
    proof = build_core_loop_proof(**kw)
    assert proof["terminal_status"] in ("freeze", "block")
    assert proof["primary_reason"]["primary_canonical_reason"] != "CORE_LOOP_PASS"


# --- 12. trace continuity gate -----------------------------------------


def test_cl26_trace_continuity_false_when_any_transition_failed() -> None:
    kw = _baseline()
    kw["execution_envelope"]["trace_id"] = ""
    proof = build_core_loop_proof(**kw)
    assert proof["trace_continuity_ok"] is False
