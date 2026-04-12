from __future__ import annotations

import copy

import pytest

from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.sel_enforcement_foundation import (
    SELEnforcementError,
    build_enforcement_action_record,
    build_enforcement_bundle,
    build_enforcement_conflict_record,
    build_enforcement_effectiveness_record,
    build_enforcement_readiness,
    build_enforcement_result_record,
    evaluate_enforcement_action,
    validate_enforcement_replay,
    verify_sel_boundary_inputs,
)


def _decision_record() -> dict:
    artifact = load_example("continuation_decision_record")
    artifact["decision_outcome"] = "continue_repair_bounded"
    artifact["reason_codes"] = ["bounded_continue_permitted"]
    artifact["trace_id"] = "trace-sel-001"
    return artifact


def _decision_bundle() -> dict:
    artifact = load_example("decision_bundle")
    artifact["trace_id"] = "trace-sel-001"
    return artifact


def _evidence_bundle() -> dict:
    artifact = load_example("decision_evidence_pack")
    artifact["trace_id"] = "trace-sel-001"
    return artifact


def test_sel_end_to_end_foundation() -> None:
    decision = _decision_record()
    bundle = _decision_bundle()
    evidence = _evidence_bundle()

    verify_sel_boundary_inputs(decision_record=decision, decision_bundle=bundle, evidence_bundle=evidence)
    action = build_enforcement_action_record(
        decision_record=decision,
        decision_bundle=bundle,
        evidence_refs=["decision_evidence_pack:cde-ep-0123456789abcdef"],
    )
    eval_result = evaluate_enforcement_action(decision_record=decision, action_record=action, evidence_bundle=evidence)
    readiness = build_enforcement_readiness(decision_record=decision, action_record=action, eval_result=eval_result)
    conflict = build_enforcement_conflict_record(decision_record=decision, action_record=action, eval_result=eval_result)
    result = build_enforcement_result_record(
        decision_record=decision,
        action_record=action,
        eval_result=eval_result,
        readiness_record=readiness,
        conflict_record=conflict,
    )
    bundle_artifact = build_enforcement_bundle(
        action_record=action,
        result_record=result,
        eval_result=eval_result,
        readiness_record=readiness,
        conflict_record=conflict,
    )
    replay = validate_enforcement_replay(
        decision_record=decision,
        action_record=action,
        first_result=result,
        replay_result=copy.deepcopy(result),
        evidence_refs=["decision_evidence_pack:cde-ep-0123456789abcdef"],
    )
    effectiveness = build_enforcement_effectiveness_record(
        decision_record=decision,
        action_record=action,
        result_record=result,
        observed_outcome="improved",
        observed_outcome_ref="outcome:sel-001",
    )

    for artifact_type, artifact in (
        ("enforcement_action_record", action),
        ("enforcement_eval_result", eval_result),
        ("enforcement_readiness_record", readiness),
        ("enforcement_conflict_record", conflict),
        ("enforcement_result_record", result),
        ("enforcement_bundle", bundle_artifact),
        ("enforcement_conflict_record", replay),
        ("enforcement_effectiveness_record", effectiveness),
    ):
        validate_artifact(artifact, artifact_type)

    assert eval_result["result"] == "pass"
    assert readiness["candidate_ready"] is True
    assert result["enforcement_status"] == "enforced"
    assert replay["result"] == "pass"


def test_rt1_boundary_integrity_missing_required_fields_fails_closed() -> None:
    decision = _decision_record()
    bundle = _decision_bundle()
    malformed = _evidence_bundle()
    malformed["artifact_type"] = "ungoverned_input"

    with pytest.raises(SELEnforcementError):
        verify_sel_boundary_inputs(decision_record=decision, decision_bundle=bundle, evidence_bundle=malformed)


def test_rt2_semantic_logic_mismatch_blocks_and_records_conflict() -> None:
    decision = _decision_record()
    bundle = _decision_bundle()
    evidence = _evidence_bundle()
    action = build_enforcement_action_record(
        decision_record=decision,
        decision_bundle=bundle,
        evidence_refs=["decision_evidence_pack:cde-ep-0123456789abcdef"],
        requested_action="none",
    )

    eval_result = evaluate_enforcement_action(decision_record=decision, action_record=action, evidence_bundle=evidence)
    readiness = build_enforcement_readiness(decision_record=decision, action_record=action, eval_result=eval_result)
    conflict = build_enforcement_conflict_record(decision_record=decision, action_record=action, eval_result=eval_result)
    result = build_enforcement_result_record(
        decision_record=decision,
        action_record=action,
        eval_result=eval_result,
        readiness_record=readiness,
        conflict_record=conflict,
    )

    assert "decision_action_mismatch" in eval_result["fail_reasons"]
    assert readiness["candidate_ready"] is False
    assert conflict["result"] == "fail"
    assert result["enforcement_status"] == "blocked"


def test_rt3_replay_drift_detected() -> None:
    decision = _decision_record()
    bundle = _decision_bundle()
    evidence = _evidence_bundle()
    action = build_enforcement_action_record(
        decision_record=decision,
        decision_bundle=bundle,
        evidence_refs=["decision_evidence_pack:cde-ep-0123456789abcdef"],
    )
    eval_result = evaluate_enforcement_action(decision_record=decision, action_record=action, evidence_bundle=evidence)
    readiness = build_enforcement_readiness(decision_record=decision, action_record=action, eval_result=eval_result)
    conflict = build_enforcement_conflict_record(decision_record=decision, action_record=action, eval_result=eval_result)
    result = build_enforcement_result_record(
        decision_record=decision,
        action_record=action,
        eval_result=eval_result,
        readiness_record=readiness,
        conflict_record=conflict,
    )

    drifted = copy.deepcopy(result)
    drifted["enforcement_status"] = "blocked"
    replay = validate_enforcement_replay(
        decision_record=decision,
        action_record=action,
        first_result=result,
        replay_result=drifted,
        evidence_refs=["decision_evidence_pack:cde-ep-0123456789abcdef"],
    )

    assert replay["result"] == "fail"
    assert "enforcement_replay_mismatch" in replay["conflict_refs"]


def test_rt4_combinatorial_attack_blocks() -> None:
    decision = _decision_record()
    bundle = _decision_bundle()
    evidence = _evidence_bundle()
    action = build_enforcement_action_record(
        decision_record=decision,
        decision_bundle=bundle,
        evidence_refs=["decision_evidence_pack:cde-ep-0123456789abcdef"],
        requested_action="quarantine",
    )
    action["non_authority_assertions"] = ["sel_enforcement_only"]

    eval_result = evaluate_enforcement_action(decision_record=decision, action_record=action, evidence_bundle=evidence)
    readiness = build_enforcement_readiness(decision_record=decision, action_record=action, eval_result=eval_result)

    assert eval_result["result"] == "fail"
    assert "decision_action_mismatch" in eval_result["fail_reasons"]
    assert "non_decision_assertion_missing" in eval_result["fail_reasons"]
    assert readiness["candidate_ready"] is False


def test_rt5_operational_reality_noop_abuse_detected() -> None:
    decision = _decision_record()
    bundle = _decision_bundle()
    evidence = _evidence_bundle()

    action = build_enforcement_action_record(
        decision_record=decision,
        decision_bundle=bundle,
        evidence_refs=["decision_evidence_pack:cde-ep-0123456789abcdef"],
        requested_action="none",
    )
    eval_result = evaluate_enforcement_action(decision_record=decision, action_record=action, evidence_bundle=evidence)
    readiness = build_enforcement_readiness(decision_record=decision, action_record=action, eval_result=eval_result)

    assert "no_op_not_ready" in readiness["blocking_reasons"]
    assert readiness["candidate_ready"] is False
