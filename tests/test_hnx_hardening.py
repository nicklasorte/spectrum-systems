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
    build_hnx_feedback_record,
    build_hnx_maintain_cycle_record,
    build_hnx_readiness_certification,
    compile_feedback_to_eval,
    compute_harness_effectiveness,
    emit_hnx_control_signal,
    enforce_hnx_boundary,
    evaluate_feedback_completeness_gate,
    evaluate_harness_contracts,
    evaluate_stage_transition,
    feedback_to_contract_tightening,
    route_hnx_feedback,
    run_hnx_boundary_redteam,
    run_hnx_semantic_redteam,
    validate_checkpoint_resume_integrity,
    validate_harness_replay,
    validate_stop_conditions,
    verify_hnx_closeout_gate,
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
        "hnx_feedback_record",
        "hnx_feedback_routing_record",
        "hnx_feedback_eval_scaffold",
        "hnx_contract_tightening_record",
        "hnx_control_signal_record",
        "hnx_feedback_gate_decision",
        "hnx_readiness_certification_record",
        "hnx_maintain_cycle_record",
    ):
        validate_artifact(load_example(name), name)


def test_boundary_fencing_blocks_forbidden_owner_overlap() -> None:
    failures = enforce_hnx_boundary(
        consumed_inputs=["hnx_stage_contract_record", "pqx_execution_result"],
        emitted_outputs=["hnx_harness_eval_result", "promotion_decision_record"],
    )
    assert "invalid_hnx_upstream_input:pqx_execution_result" in failures
    assert "invalid_hnx_downstream_output:promotion_decision_record" in failures


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
        stop_required=True,
    )
    assert skipped["allowed"] is False
    assert "STAGE_SKIP_DETECTED" in skipped["reason_codes"]
    assert "HUMAN_CHECKPOINT_REQUIRED" in skipped["reason_codes"]
    assert "STOP_REQUIRED_TRANSITION_BLOCK" in skipped["reason_codes"]


def test_harness_eval_checkpoint_resume_and_readiness_fail_closed() -> None:
    fx = _fixtures()
    eval_result = evaluate_harness_contracts(
        stage_contract=fx["stage_contract"],
        checkpoint_record=fx["checkpoint"],
        resume_record=fx["resume"],
        continuity_state=fx["continuity"],
        stop_condition_record=fx["stop"],
        expected_lineage_chain=["AEX", "TLC", "TPA", "PQX"],
        evaluated_at="2026-04-16T00:06:00Z",
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
        created_at="2026-04-16T00:06:00Z",
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
        evaluated_at="2026-04-16T00:06:00Z",
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
        created_at="2026-04-16T00:06:00Z",
    )
    replay_ok, replay_fails = validate_harness_replay(
        prior_bundle=bundle,
        replay_bundle=copy.deepcopy(bundle),
        prior_eval=eval_result,
        replay_eval=copy.deepcopy(eval_result),
    )
    assert replay_ok is True
    assert replay_fails == []


def test_hidden_state_variance_detection_blocks() -> None:
    fx = _fixtures()
    eval_result = evaluate_harness_contracts(
        stage_contract=fx["stage_contract"],
        checkpoint_record=fx["checkpoint"],
        resume_record=fx["resume"],
        continuity_state=fx["continuity"],
        stop_condition_record=fx["stop"],
        expected_lineage_chain=["AEX", "TLC", "TPA", "PQX"],
        evaluated_at="2026-04-16T00:06:00Z",
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
        created_at="2026-04-16T00:06:00Z",
    )
    replay_eval = copy.deepcopy(eval_result)
    replay_eval["fail_reasons"] = ["REPLAY_OUTPUT_DRIFT"]
    ok, fails = validate_harness_replay(
        prior_bundle=bundle,
        replay_bundle=copy.deepcopy(bundle),
        prior_eval=eval_result,
        replay_eval=replay_eval,
        prior_runs=[eval_result],
    )
    assert ok is False
    assert "HIDDEN_STATE_VARIANCE_DETECTED" in fails


def test_feedback_router_and_gate_behavior() -> None:
    feedback = build_hnx_feedback_record(
        created_at="2026-04-16T01:00:00Z",
        trace_id="trace-hnx-1",
        source="replay",
        stage_ref="checkpointed->resumed",
        failure_type="replay_mismatch",
        severity="critical",
        affected_artifact_ids=["hnx_checkpoint_record:cp-1"],
        reproduction_context="deterministic replay produced mismatch",
        structural_root_cause="resume linkage incomplete",
        recommended_action="tighten contract + add eval",
        requires_eval_update=True,
        requires_contract_update=True,
        requires_policy_signal=True,
        resolution_status="open",
        resolution_refs=[],
    )
    routes = route_hnx_feedback(feedback_record=feedback, created_at="2026-04-16T01:01:00Z")
    assert "eval_expansion" in routes["routes"]
    assert "redteam_regression_bundle" in routes["routes"]

    scaffold = compile_feedback_to_eval(feedback_record=feedback, created_at="2026-04-16T01:02:00Z")
    assert scaffold["eval_family"] == "replay_mismatch_eval"

    tightening = feedback_to_contract_tightening(feedback_record=feedback, created_at="2026-04-16T01:03:00Z")
    assert "required_continuity_artifacts" in tightening["required_contract_fields"]

    gate = evaluate_feedback_completeness_gate(feedback_records=[feedback], created_at="2026-04-16T01:04:00Z")
    assert gate["decision"] == "block"


def test_integration_hnx_pqx_tlc_signal_and_certification_path() -> None:
    fx = _fixtures()
    eval_result = evaluate_harness_contracts(
        stage_contract=fx["stage_contract"],
        checkpoint_record=fx["checkpoint"],
        resume_record=fx["resume"],
        continuity_state=fx["continuity"],
        stop_condition_record=fx["stop"],
        expected_lineage_chain=["AEX", "TLC", "TPA", "PQX"],
        evaluated_at="2026-04-16T01:10:00Z",
    )
    feedback = build_hnx_feedback_record(
        created_at="2026-04-16T01:11:00Z",
        trace_id="trace-hnx-1",
        source="handoff",
        stage_ref="candidate_ready->checkpointed",
        failure_type="handoff_incomplete",
        severity="high",
        affected_artifact_ids=["handoff_record:1"],
        reproduction_context="missing semantic transfer field",
        structural_root_cause="handoff contract incompleteness",
        recommended_action="add completeness eval",
        requires_eval_update=True,
        requires_contract_update=True,
        requires_policy_signal=True,
        resolution_status="in_progress",
        resolution_refs=["docs/reviews/HNX-01-redteam-review-1.md"],
    )
    gate = evaluate_feedback_completeness_gate(feedback_records=[feedback], created_at="2026-04-16T01:12:00Z")
    assert gate["decision"] == "freeze"

    debt = build_continuity_debt_record(
        run_id="run-1",
        trace_id="trace-hnx-1",
        violations=["CHECKPOINT_STALE", "CHECKPOINT_STALE", "HANDOFF_INCOMPLETE"],
        created_at="2026-04-16T01:13:00Z",
    )
    effectiveness = compute_harness_effectiveness(
        window_id="win-1",
        created_at="2026-04-16T01:14:00Z",
        outcomes=[
            {
                "completed": True,
                "broken_resume": False,
                "stop_bypass_blocked": True,
                "invalid_transition": False,
                "handoff_complete": True,
                "stale_checkpoint": False,
                "replay_mismatch": False,
                "unresolved_feedback": False,
            },
            {
                "completed": False,
                "broken_resume": True,
                "stop_bypass_blocked": True,
                "invalid_transition": True,
                "handoff_complete": False,
                "stale_checkpoint": True,
                "replay_mismatch": True,
                "unresolved_feedback": True,
            },
        ],
    )
    signal = emit_hnx_control_signal(
        effectiveness_record=effectiveness,
        unresolved_feedback_count=1,
        continuity_debt_record=debt,
        created_at="2026-04-16T01:15:00Z",
    )
    assert signal["non_authority_note"].startswith("signal_only")

    cert = build_hnx_readiness_certification(
        run_id="run-1",
        trace_id="trace-hnx-1",
        harness_eval=eval_result,
        replay_pass=True,
        trace_complete=True,
        required_eval_complete=True,
        feedback_gate={"decision": "allow"},
        redteam_clean=True,
        non_authority_proof_refs=["docs/architecture/system_registry.md#hnx"],
        created_at="2026-04-16T01:16:00Z",
    )
    assert cert["status"] == "pass"

    maintain = build_hnx_maintain_cycle_record(
        maintain_cycle_id="mnt-1",
        trace_id="trace-hnx-1",
        continuity_drift_detected=True,
        stage_contract_drift_detected=False,
        docs_runtime_drift_detected=False,
        incidents_converted_to_evals=["hnx_feedback_eval_scaffold:1"],
        structural_debt_refs=["hnx_continuity_debt_record:1"],
        created_at="2026-04-16T01:17:00Z",
    )
    assert maintain["maintain_status"] == "action_required"


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
        created_at="2026-04-16T00:06:00Z",
    )
    assert len(conflict["conflict_codes"]) == 2


def test_harness_effectiveness_requires_outcomes() -> None:
    with pytest.raises(HNXHardeningError, match="harness_effectiveness_requires_outcomes"):
        compute_harness_effectiveness(window_id="win", created_at="2026-04-16T00:06:00Z", outcomes=[])


def test_hnx_closeout_gate_is_operationally_real() -> None:
    fx = _fixtures()
    eval_result = evaluate_harness_contracts(
        stage_contract=fx["stage_contract"],
        checkpoint_record=fx["checkpoint"],
        resume_record=fx["resume"],
        continuity_state=fx["continuity"],
        stop_condition_record=fx["stop"],
        expected_lineage_chain=["AEX", "TLC", "TPA", "PQX"],
        evaluated_at="2026-04-16T00:00:00Z",
    )
    readiness = build_harness_readiness(
        run_id="run-closeout",
        trace_id="trace-hnx-closeout",
        eval_result=eval_result,
        continuity_failures=[],
        created_at="2026-04-16T00:00:00Z",
    )
    closeout = verify_hnx_closeout_gate(
        harness_eval=eval_result,
        readiness=readiness,
        replay_match=True,
        stop_failures=[],
        checkpoint_resume_failures=[],
    )
    assert closeout["closeout_status"] == "closed"
