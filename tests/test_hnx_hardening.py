from __future__ import annotations

import copy

import pytest

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.hnx_hardening import (
    HNXHardeningError,
    build_continuity_debt_record,
    build_harness_bundle,
    build_harness_readiness,
    build_hnx_conflict_record,
    compute_harness_effectiveness,
    enforce_hnx_boundary,
    evaluate_harness_contracts,
    evaluate_stage_transition,
    run_hnx_boundary_redteam,
    run_hnx_semantic_redteam,
    validate_checkpoint_resume_integrity,
    validate_harness_replay,
    validate_stop_conditions,
)


def _fixtures() -> dict[str, dict]:
    return {
        "stage_contract": load_example("hnx_stage_contract_record"),
        "checkpoint": load_example("hnx_checkpoint_record"),
        "resume": load_example("hnx_resume_record"),
        "continuity": load_example("hnx_continuity_state_record"),
        "stop": load_example("hnx_stop_condition_record"),
    }


def test_hnx_contract_examples_validate() -> None:
    for name in (
        "hnx_stage_contract_record",
        "hnx_checkpoint_record",
        "hnx_resume_record",
        "hnx_continuity_state_record",
        "hnx_stop_condition_record",
        "hnx_harness_eval_result",
        "hnx_harness_readiness_record",
        "hnx_harness_conflict_record",
        "hnx_harness_bundle",
        "hnx_harness_effectiveness_record",
        "hnx_continuity_debt_record",
    ):
        validate_artifact(load_example(name), name)


def test_boundary_fencing_blocks_forbidden_owner_overlap() -> None:
    failures = enforce_hnx_boundary(
        consumed_inputs=["hnx_stage_contract_record", "pqx_execution_result"],
        emitted_outputs=["hnx_harness_eval_result", "cde_closeout_decision"],
    )
    assert "invalid_hnx_upstream_input:pqx_execution_result" in failures
    assert "invalid_hnx_downstream_output:cde_closeout_decision" in failures


def test_deterministic_stage_machine_and_stage_skip_detector() -> None:
    ok = evaluate_stage_transition(
        from_state="initialized",
        to_state="candidate_ready",
        stage_index=0,
        next_stage_index=1,
        required_human_checkpoint=False,
        human_checkpoint_recorded=False,
    )
    assert ok["allowed"] is True

    skipped = evaluate_stage_transition(
        from_state="candidate_ready",
        to_state="resumed",
        stage_index=1,
        next_stage_index=4,
        required_human_checkpoint=True,
        human_checkpoint_recorded=False,
    )
    assert skipped["allowed"] is False
    assert "STAGE_SKIP_DETECTED" in skipped["reason_codes"]
    assert "HUMAN_CHECKPOINT_REQUIRED" in skipped["reason_codes"]


def test_harness_eval_checkpoint_resume_and_readiness_fail_closed() -> None:
    fx = _fixtures()
    eval_result = evaluate_harness_contracts(
        stage_contract=fx["stage_contract"],
        checkpoint_record=fx["checkpoint"],
        resume_record=fx["resume"],
        continuity_state=fx["continuity"],
        stop_condition_record=fx["stop"],
        expected_lineage_chain=["AEX", "TLC", "TPA", "PQX"],
        evaluated_at="2026-04-12T00:06:00Z",
    )
    assert eval_result["evaluation_status"] == "pass"

    stale_checkpoint = copy.deepcopy(fx["checkpoint"])
    stale_checkpoint["created_epoch_minutes"] = 1
    integrity_failures = validate_checkpoint_resume_integrity(
        checkpoint_record=stale_checkpoint,
        resume_record=fx["resume"],
        continuity_state=fx["continuity"],
        now_epoch_minutes=200,
    )
    assert "CHECKPOINT_STALE" in integrity_failures

    readiness = build_harness_readiness(
        run_id="run-1",
        trace_id="trace-hnx-1",
        eval_result=eval_result,
        continuity_failures=integrity_failures,
        created_at="2026-04-12T00:06:00Z",
    )
    assert readiness["readiness_status"] == "blocked"


def test_stop_condition_integrity_and_replay_validation() -> None:
    fx = _fixtures()
    stop = copy.deepcopy(fx["stop"])
    stop["stop_required"] = True
    stop["human_checkpoint_recorded"] = False
    fails = validate_stop_conditions(stop_condition_record=stop, requested_transition="resumed")
    assert "STOP_CONDITION_BYPASS" in fails
    assert "HUMAN_CHECKPOINT_BYPASS" in fails

    eval_result = evaluate_harness_contracts(
        stage_contract=fx["stage_contract"],
        checkpoint_record=fx["checkpoint"],
        resume_record=fx["resume"],
        continuity_state=fx["continuity"],
        stop_condition_record=fx["stop"],
        expected_lineage_chain=["AEX", "TLC", "TPA", "PQX"],
        evaluated_at="2026-04-12T00:06:00Z",
    )
    bundle = build_harness_bundle(
        run_id="run-1",
        trace_id="trace-hnx-1",
        stage_contract=fx["stage_contract"],
        checkpoint_record=fx["checkpoint"],
        resume_record=fx["resume"],
        continuity_state=fx["continuity"],
        stop_condition_record=fx["stop"],
        eval_result=eval_result,
        created_at="2026-04-12T00:06:00Z",
    )
    replay_ok, replay_fails = validate_harness_replay(
        prior_bundle=bundle,
        replay_bundle=copy.deepcopy(bundle),
        prior_eval=eval_result,
        replay_eval=copy.deepcopy(eval_result),
    )
    assert replay_ok is True
    assert replay_fails == []


def test_rt1_rt2_exploits_converted_to_regressions_and_fixes() -> None:
    rt1_findings = run_hnx_boundary_redteam(
        fixtures=[
            {"fixture_id": "RT1-STAGE-BYPASS", "expected": "blocked", "observed": "accepted"},
            {"fixture_id": "RT1-MALFORMED-CHECKPOINT", "expected": "blocked", "observed": "blocked"},
        ]
    )
    assert [row["fixture_id"] for row in rt1_findings] == ["RT1-STAGE-BYPASS"]

    rt2_findings = run_hnx_semantic_redteam(
        fixtures=[
            {"fixture_id": "RT2-CONTEXT-ROT", "semantic_risk": True, "observed": "accepted"},
            {"fixture_id": "RT2-LONG-HORIZON-STOP-BYPASS", "semantic_risk": True, "observed": "blocked"},
        ]
    )
    assert [row["fixture_id"] for row in rt2_findings] == ["RT2-CONTEXT-ROT"]

    conflict = build_hnx_conflict_record(
        run_id="run-1",
        trace_id="trace-hnx-1",
        conflict_codes=["RT1-STAGE-BYPASS", "RT2-CONTEXT-ROT"],
        created_at="2026-04-12T00:06:00Z",
    )
    assert len(conflict["conflict_codes"]) == 2

    debt = build_continuity_debt_record(
        run_id="run-1",
        trace_id="trace-hnx-1",
        violations=["CHECKPOINT_STALE", "CHECKPOINT_STALE", "STAGE_SKIP_DETECTED"],
        created_at="2026-04-12T00:06:00Z",
    )
    assert debt["debt_status"] == "elevated"
    assert "CHECKPOINT_STALE" in debt["repeat_violation_codes"]


def test_harness_effectiveness_requires_outcomes() -> None:
    with pytest.raises(HNXHardeningError, match="harness_effectiveness_requires_outcomes"):
        compute_harness_effectiveness(window_id="win", created_at="2026-04-12T00:06:00Z", outcomes=[])

    artifact = compute_harness_effectiveness(
        window_id="win",
        created_at="2026-04-12T00:06:00Z",
        outcomes=[
            {"completed": True, "broken_resume": False, "stop_bypass_blocked": True},
            {"completed": False, "broken_resume": True, "stop_bypass_blocked": True},
        ],
    )
    assert artifact["runs_evaluated"] == 2
