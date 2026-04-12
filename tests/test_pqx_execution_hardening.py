from __future__ import annotations

from copy import deepcopy

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.pqx_execution_hardening import (
    build_execution_bundle,
    build_execution_effectiveness_record,
    build_execution_recurrence_record,
    build_pqx_execution_conflict_record,
    build_pqx_execution_eval_result,
    build_pqx_execution_readiness_record,
    enforce_execution_transition,
    run_boundary_redteam_round,
    validate_execution_replay,
)


def _fixture() -> dict:
    return {
        "run_id": "run-pqx-001",
        "trace_id": "trace:pqx:001",
        "slice_id": "PQX-QUEUE-01",
        "wrapper": {
            "artifact_type": "codex_pqx_task_wrapper",
            "lineage_path": ["AEX", "TLC", "TPA", "PQX"],
            "freshness": {"status": "fresh", "age_hours": 1},
            "fix_slice_ref": "review_fix_slice:1",
        },
        "tpa_slice_artifact": {
            "artifact_type": "tpa_slice_artifact",
            "allowed_scope": ["tests/test_pqx_execution_hardening.py"],
            "complexity_budget": {"max_units": 4},
        },
        "top_level_conductor_run_artifact": {
            "artifact_type": "top_level_conductor_run_artifact",
            "run_id": "run-pqx-001",
        },
        "execution_result": {
            "execution_status": "success",
            "changed_paths": ["tests/test_pqx_execution_hardening.py"],
            "complexity_units": 2,
            "slice_execution_record_ref": "data/pqx/r1.record.json",
            "audit_bundle_ref": "data/pqx/r1.audit.json",
            "replay_result_ref": "data/pqx/r1.replay.json",
            "trace_refs": ["trace:1", "trace:2"],
            "execution_path": "bounded",
            "closure_authority_requested": False,
            "meaningful_output_count": 1,
            "slice_id": "PQX-QUEUE-01",
            "intended_outcome_ref": "goal:bounded-execution",
        },
        "review_handoff": {"fix_slice_ref": "review_fix_slice:1"},
        "prior_attempts": [],
    }


def test_contract_examples_validate_for_pqx_hardening_artifacts() -> None:
    for name in (
        "pqx_execution_eval_result",
        "pqx_execution_readiness_record",
        "pqx_execution_conflict_record",
        "pqx_execution_bundle",
        "pqx_execution_effectiveness_record",
        "pqx_execution_recurrence_record",
    ):
        validate_artifact(load_example(name), name)


def test_eval_harness_passes_for_valid_inputs_and_builds_bundle_chain() -> None:
    f = _fixture()
    eval_result = build_pqx_execution_eval_result(**f)
    readiness = build_pqx_execution_readiness_record(eval_result=eval_result)
    conflict = build_pqx_execution_conflict_record(eval_result=deepcopy(eval_result | {"fail_reasons": ["scope_compliant"]}))
    effectiveness = build_execution_effectiveness_record(execution_result=f["execution_result"], eval_result=eval_result)
    recurrence = build_execution_recurrence_record(run_id=f["run_id"], history=[{"fail_reasons": [], "retry_loop_detected": False}])
    replay = validate_execution_replay(
        baseline={"wrapper_fingerprint": "a", "tpa_fingerprint": "b", "result_fingerprint": "c", "terminal_state": "completed"},
        replay={"wrapper_fingerprint": "a", "tpa_fingerprint": "b", "result_fingerprint": "c", "terminal_state": "completed"},
    )
    bundle = build_execution_bundle(
        run_id=f["run_id"],
        trace_id=f["trace_id"],
        wrapper_ref="codex_pqx_task_wrapper:abc",
        tpa_ref="tpa_slice_artifact:abc",
        tlc_ref="top_level_conductor_run_artifact:abc",
        eval_result=eval_result,
        readiness_record=readiness,
        replay_validation=replay,
        effectiveness_record=effectiveness,
        recurrence_record=recurrence,
    )
    assert eval_result["status"] == "pass"
    assert readiness["status"] == "candidate_ready"
    assert conflict["reason_codes"] == ["scope_compliant"]
    assert bundle["replay_validation"]["is_match"] is True


def test_eval_harness_fails_closed_on_boundary_violations() -> None:
    f = _fixture()
    f["wrapper"]["lineage_path"] = ["AEX", "TPA", "PQX"]
    f["wrapper"]["freshness"] = {"status": "stale", "age_hours": 48}
    f["execution_result"]["meaningful_output_count"] = 0
    eval_result = build_pqx_execution_eval_result(**f)
    assert eval_result["status"] == "fail"
    assert "lineage_valid" in eval_result["fail_reasons"]
    assert "wrapper_stale" in eval_result["fail_reasons"]
    assert "no_op_success_guard" in eval_result["fail_reasons"]


def test_replay_validation_detects_drift_and_state_transitions_are_deterministic() -> None:
    assert enforce_execution_transition(prior_state="queued", next_state="running")["terminal"] is False
    assert enforce_execution_transition(prior_state="running", next_state="completed")["terminal"] is True
    replay = validate_execution_replay(
        baseline={"wrapper_fingerprint": "a", "tpa_fingerprint": "b", "result_fingerprint": "c", "terminal_state": "completed"},
        replay={"wrapper_fingerprint": "a", "tpa_fingerprint": "b", "result_fingerprint": "x", "terminal_state": "completed"},
    )
    assert replay["is_match"] is False
    assert replay["reason_codes"] == ["replay_mismatch_detected"]


def test_redteam_rounds_block_fail_open_cases() -> None:
    base = _fixture()
    rt1 = run_boundary_redteam_round(round_id="PQX-RT1", base_fixture=base)
    rt2 = run_boundary_redteam_round(round_id="PQX-RT2", base_fixture=base)
    assert rt1["status"] == "pass"
    assert rt2["status"] == "pass"
    assert rt1["exploits"] == []
    assert rt2["exploits"] == []
