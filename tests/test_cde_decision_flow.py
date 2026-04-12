from __future__ import annotations

import json

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.cde_decision_flow import (
    CDEDecisionFlowError,
    build_cde_closeout_gate_record,
    build_decision_bundle,
    build_decision_effectiveness_record,
    build_decision_evidence_pack,
    build_decision_readiness,
    detect_decision_conflicts,
    evaluate_decision,
    make_continuation_decision,
    validate_decision_replay,
    verify_cde_boundary_inputs,
)
from spectrum_systems.modules.runtime.fre_repair_flow import (
    build_repair_bundle,
    build_repair_effectiveness_record,
    build_repair_readiness_candidate,
    build_repair_recurrence_record,
    evaluate_repair_candidate,
    generate_repair_candidate,
)
from spectrum_systems.modules.runtime.ril_interpretation import (
    build_ambiguity_signal,
    build_interpretation_bundle,
    build_interpretation_record,
    build_readiness_record,
    detect_contradictions,
    evaluate_interpretation,
    normalize_failure_packet,
    validate_interpretation_repair_alignment,
    validate_replay,
    verify_ril_closeout,
)


def _evidence() -> dict:
    return {
        "artifact_type": "execution_failure_packet",
        "source_artifact_ref": "execution_failure_packet:efp-100",
        "failure_class": "slice_contract_mismatch",
        "owner_surface": "RIL",
        "source_evidence_refs": ["trace:trace-cde-001"],
        "lineage_refs": ["lineage:ril-001"],
        "ambiguity_refs": [],
        "contradiction_refs": [],
    }


def _fre_packet() -> dict:
    return {
        "artifact_type": "execution_failure_packet",
        "failure_packet_id": "efp-100",
        "classified_failure_type": "slice_contract_mismatch",
        "affected_artifact_refs": ["contracts/examples/review_control_signal_artifact.json"],
        "trace_refs": ["trace:trace-cde-001"],
        "validation_refs": ["pytest:tests/test_cde_decision_flow.py::test_cde_flow_end_to_end"],
    }


def _build_ril_fre_artifacts() -> tuple[dict, dict, dict]:
    failure_packet = normalize_failure_packet(evidence=_evidence(), trace_id="trace-cde-001")
    conflict = detect_contradictions(failure_packet=failure_packet, evidence_refs=["trace:cde-ok"], material_threshold=2)
    interpretation = build_interpretation_record(
        failure_packet=failure_packet,
        conflict_record=conflict,
        interpretation_notes=["normalized failure packet for bounded decisioning"],
    )
    eval_result = evaluate_interpretation(interpretation_record=interpretation, conflict_record=conflict)
    readiness = build_readiness_record(interpretation_record=interpretation, eval_result=eval_result)
    interpretation_bundle = build_interpretation_bundle(
        failure_packet=failure_packet,
        interpretation_record=interpretation,
        eval_result=eval_result,
        readiness_record=readiness,
        conflict_record=conflict,
    )
    replay = validate_replay(source_inputs=[_evidence()], first_outputs=[failure_packet], replay_outputs=[dict(failure_packet)], schema_version="1.0.0")

    repair_candidate = generate_repair_candidate(failure_packet=_fre_packet(), trace_id="trace-cde-001")
    repair_eval = evaluate_repair_candidate(repair_candidate=repair_candidate)
    repair_eff = build_repair_effectiveness_record(repair_candidate=repair_candidate, repair_eval_result=repair_eval)
    repair_rec = build_repair_recurrence_record(repair_candidate=repair_candidate, recurrence_count=1, cluster_key="slice_contract_mismatch::cde")
    repair_ready = build_repair_readiness_candidate(repair_candidate=repair_candidate, repair_eval_result=repair_eval)
    repair_bundle = build_repair_bundle(
        repair_candidate=repair_candidate,
        repair_eval_result=repair_eval,
        repair_effectiveness_record=repair_eff,
        repair_recurrence_record=repair_rec,
        repair_readiness_candidate=repair_ready,
    )
    alignment = validate_interpretation_repair_alignment(interpretation_record=interpretation, repair_candidate=repair_candidate)
    ambiguity = build_ambiguity_signal(interpretation_records=[interpretation], ambiguity_budget=0.4)

    closeout = verify_ril_closeout(
        failure_packet=failure_packet,
        interpretation_record=interpretation,
        eval_result=eval_result,
        readiness_record=readiness,
        replay_validation_record=replay,
        conflict_record=conflict,
        alignment_record=alignment,
        ambiguity_signal=ambiguity,
    )
    validate_artifact(closeout, "ril_closeout_gate_record")
    assert closeout["ril_operational"] is True

    return interpretation_bundle, repair_bundle, conflict


def test_cde_flow_end_to_end() -> None:
    interpretation_bundle, repair_bundle, _ = _build_ril_fre_artifacts()

    evidence_pack = build_decision_evidence_pack(
        trace_id="trace-cde-001",
        interpretation_bundle=interpretation_bundle,
        repair_bundle=repair_bundle,
        policy_constraints_ref="policy:cde_bounded_decision_v1",
        provenance_refs=["provenance_record:prv-001"],
        replay_refs=["interpretation_replay_validation_record:ril-replay-001"],
        evidence_refs=["failure_packet:ril-fp-001", "repair_eval_result:fre-reval-001", "policy:cde_bounded_decision_v1"],
    )
    conflict_record = detect_decision_conflicts(evidence_pack=evidence_pack, conflict_refs=["interpretation_conflict_record:ril-conf-pass"], material_threshold=2)
    decision = make_continuation_decision(evidence_pack=evidence_pack, conflict_record=conflict_record, evidence_budget_min=2, ambiguity_rate=0.1)
    eval_result = evaluate_decision(decision_record=decision, conflict_record=conflict_record, evidence_pack=evidence_pack)
    readiness = build_decision_readiness(decision_record=decision, eval_result=eval_result)
    bundle = build_decision_bundle(
        evidence_pack=evidence_pack,
        decision_record=decision,
        eval_result=eval_result,
        readiness_record=readiness,
        conflict_record=conflict_record,
    )
    replay = validate_decision_replay(evidence_pack=evidence_pack, first_decision=decision, replay_decision=dict(decision))
    effectiveness = build_decision_effectiveness_record(
        decision_record=decision,
        downstream_outcome_ref="downstream_outcome:tlc-001",
        downstream_outcome="improved",
    )

    closeout = build_cde_closeout_gate_record(
        decision_bundle=bundle,
        decision_eval_result=eval_result,
        decision_replay_validation_record=replay,
        decision_effectiveness_record=effectiveness,
    )

    for artifact_type, artifact in (
        ("decision_evidence_pack", evidence_pack),
        ("decision_conflict_record", conflict_record),
        ("continuation_decision_record", decision),
        ("decision_eval_result", eval_result),
        ("decision_readiness_record", readiness),
        ("decision_bundle", bundle),
        ("decision_replay_validation_record", replay),
        ("decision_effectiveness_record", effectiveness),
        ("cde_closeout_gate_record", closeout),
    ):
        validate_artifact(artifact, artifact_type)

    assert decision["decision_outcome"] == "continue_repair_bounded"
    assert readiness["candidate_ready"] is True
    assert replay["result"] == "pass"
    assert closeout["closeout_status"] == "closed"


def test_cde_boundary_and_fail_closed_behaviors() -> None:
    interpretation_bundle, repair_bundle, _ = _build_ril_fre_artifacts()
    verify_cde_boundary_inputs(
        upstream_artifacts=[
            interpretation_bundle,
            repair_bundle,
            {"artifact_type": "interpretation_conflict_record", "schema_version": "1.0.0"},
        ]
    )

    try:
        verify_cde_boundary_inputs(upstream_artifacts=[{"artifact_type": "repair_candidate"}])
        raise AssertionError("expected CDEDecisionFlowError")
    except CDEDecisionFlowError as exc:
        assert "boundary" in str(exc)

    evidence_pack = build_decision_evidence_pack(
        trace_id="trace-cde-002",
        interpretation_bundle=interpretation_bundle,
        repair_bundle=repair_bundle,
        policy_constraints_ref="policy:cde_bounded_decision_v1",
        provenance_refs=["provenance_record:prv-002"],
        replay_refs=["interpretation_replay_validation_record:ril-replay-002"],
        evidence_refs=["failure_packet:ril-fp-002"],
    )
    conflict_record = detect_decision_conflicts(
        evidence_pack=evidence_pack,
        conflict_refs=["interpretation_conflict_record:ril-conf-a", "policy_conflict_record:pol-1"],
        material_threshold=1,
    )
    decision = make_continuation_decision(evidence_pack=evidence_pack, conflict_record=conflict_record, evidence_budget_min=2, ambiguity_rate=0.5)
    eval_result = evaluate_decision(decision_record=decision, conflict_record=conflict_record, evidence_pack=evidence_pack)
    readiness = build_decision_readiness(decision_record=decision, eval_result=eval_result)

    assert decision["decision_outcome"] == "human_review_required"
    assert readiness["candidate_ready"] is False

    replay_drift = validate_decision_replay(
        evidence_pack=evidence_pack,
        first_decision=decision,
        replay_decision={**decision, "decision_outcome": "block"},
    )
    assert replay_drift["result"] == "fail"
    assert "decision_replay_mismatch" in replay_drift["fail_reasons"]


def test_cde_closeout_gate_artifacts_are_operationally_real_on_repo_paths(tmp_path) -> None:
    interpretation_bundle, repair_bundle, _ = _build_ril_fre_artifacts()
    evidence_pack = build_decision_evidence_pack(
        trace_id="trace-cde-closeout-001",
        interpretation_bundle=interpretation_bundle,
        repair_bundle=repair_bundle,
        policy_constraints_ref="policy:cde_bounded_decision_v1",
        provenance_refs=["provenance_record:prv-closeout-001"],
        replay_refs=["interpretation_replay_validation_record:ril-replay-closeout-001"],
        evidence_refs=["failure_packet:ril-fp-closeout-001", "repair_eval_result:fre-reval-closeout-001", "policy:cde_bounded_decision_v1"],
    )
    conflict_record = detect_decision_conflicts(evidence_pack=evidence_pack, conflict_refs=["interpretation_conflict_record:ril-conf-closeout-001"], material_threshold=2)
    decision = make_continuation_decision(evidence_pack=evidence_pack, conflict_record=conflict_record, evidence_budget_min=2, ambiguity_rate=0.1)
    eval_result = evaluate_decision(decision_record=decision, conflict_record=conflict_record, evidence_pack=evidence_pack)
    readiness = build_decision_readiness(decision_record=decision, eval_result=eval_result)
    bundle = build_decision_bundle(
        evidence_pack=evidence_pack,
        decision_record=decision,
        eval_result=eval_result,
        readiness_record=readiness,
        conflict_record=conflict_record,
    )
    replay = validate_decision_replay(evidence_pack=evidence_pack, first_decision=decision, replay_decision=dict(decision))
    effectiveness = build_decision_effectiveness_record(
        decision_record=decision,
        downstream_outcome_ref="downstream_outcome:tlc-closeout-001",
        downstream_outcome="improved",
    )
    closeout = build_cde_closeout_gate_record(
        decision_bundle=bundle,
        decision_eval_result=eval_result,
        decision_replay_validation_record=replay,
        decision_effectiveness_record=effectiveness,
    )

    output_dir = tmp_path / "artifacts" / "cde_closeout"
    output_dir.mkdir(parents=True)
    (output_dir / "decision_bundle.json").write_text(json.dumps(bundle), encoding="utf-8")
    (output_dir / "continuation_decision_record.json").write_text(json.dumps(decision), encoding="utf-8")
    (output_dir / "decision_eval_result.json").write_text(json.dumps(eval_result), encoding="utf-8")
    (output_dir / "decision_replay_validation_record.json").write_text(json.dumps(replay), encoding="utf-8")
    (output_dir / "decision_effectiveness_record.json").write_text(json.dumps(effectiveness), encoding="utf-8")
    (output_dir / "cde_closeout_gate_record.json").write_text(json.dumps(closeout), encoding="utf-8")

    assert (output_dir / "cde_closeout_gate_record.json").exists()
    assert closeout["closeout_status"] == "closed"
    assert closeout["cde_operational"] is True
