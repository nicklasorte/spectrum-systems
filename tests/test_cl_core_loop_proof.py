"""CL-25: core loop proof — pass / block / freeze scenarios."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.governance.core_loop_proof import (
    CoreLoopProofError,
    build_core_loop_proof,
)


def _passing_kwargs():
    return dict(
        proof_id="clp-pass",
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


# --- CL-25 pass scenario ------------------------------------------------


def test_cl25_pass_scenario_terminal_status_pass() -> None:
    proof = build_core_loop_proof(**_passing_kwargs())
    assert proof["terminal_status"] == "pass"
    assert proof["primary_reason"]["primary_canonical_reason"] == "CORE_LOOP_PASS"
    assert proof["primary_reason"]["next_allowed_action"] == "allow_continuation"
    assert proof["trace_continuity_ok"] is True


def test_cl25_pass_scenario_has_all_stage_refs() -> None:
    proof = build_core_loop_proof(**_passing_kwargs())
    for stage in ("AEX", "PQX", "EVL", "TPA", "CDE", "SEL"):
        assert proof["stages"][stage]["status"] == "ok", stage
        assert proof["stages"][stage]["artifact_ref"], stage


def test_cl25_pass_scenario_human_readable_includes_proof_id() -> None:
    proof = build_core_loop_proof(**_passing_kwargs())
    assert "clp-pass" in proof["human_readable"]


def test_cl25_proof_id_required() -> None:
    kwargs = _passing_kwargs()
    kwargs["proof_id"] = ""
    with pytest.raises(CoreLoopProofError):
        build_core_loop_proof(**kwargs)


def test_cl25_lineage_and_replay_refs_propagate() -> None:
    proof = build_core_loop_proof(**_passing_kwargs())
    assert proof["lineage_chain_ref"] == "lin-1"
    assert proof["replay_record_ref"] == "rpl-1"


# --- CL-25 block scenarios ----------------------------------------------


def test_cl25_block_when_admission_missing() -> None:
    kwargs = _passing_kwargs()
    kwargs["admission_packet"] = None
    proof = build_core_loop_proof(**kwargs)
    assert proof["terminal_status"] == "block"
    assert proof["primary_reason"]["source_stage"] == "AEX"


def test_cl25_block_when_execution_envelope_missing() -> None:
    kwargs = _passing_kwargs()
    kwargs["execution_envelope"] = None
    proof = build_core_loop_proof(**kwargs)
    assert proof["terminal_status"] == "block"
    # admission still ok, primary should be execution
    assert proof["primary_reason"]["source_stage"] == "PQX"


def test_cl25_block_when_eval_required_missing() -> None:
    kwargs = _passing_kwargs()
    kwargs["eval_resolution_inputs"] = {
        "declared_catalog": [{"name": "core", "required": True}],
        "submitted_evals": [],
    }
    proof = build_core_loop_proof(**kwargs)
    assert proof["terminal_status"] == "block"
    assert proof["primary_reason"]["primary_canonical_reason"] == "EVAL_REQUIRED_MISSING"


def test_cl25_block_when_policy_input_hidden() -> None:
    kwargs = _passing_kwargs()
    kwargs["policy_inputs"]["hidden_state"] = "secret"
    proof = build_core_loop_proof(**kwargs)
    assert proof["terminal_status"] == "block"
    assert "POLICY" in proof["primary_reason"]["primary_canonical_reason"]


def test_cl25_freeze_when_decision_outcome_missing() -> None:
    kwargs = _passing_kwargs()
    kwargs["decision_outcome"] = None
    proof = build_core_loop_proof(**kwargs)
    assert proof["terminal_status"] == "freeze"
    assert proof["primary_reason"]["primary_canonical_reason"] == "DECISION_FREEZE_REQUIRED"


def test_cl25_block_when_sel_action_inconsistent_with_decision() -> None:
    kwargs = _passing_kwargs()
    kwargs["decision_outcome"] = {"decision": "block", "cde_decision_ref": "cde-blk"}
    kwargs["sel_action"] = {"action": "allow_continuation", "sel_action_ref": "sel-bad"}
    proof = build_core_loop_proof(**kwargs)
    assert proof["terminal_status"] == "block"
    primary = proof["primary_reason"]["primary_canonical_reason"]
    assert primary.startswith("ACTION_") or primary.startswith("DECISION_")
