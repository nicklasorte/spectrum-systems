from __future__ import annotations

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.fre_repair_flow import (
    build_repair_bundle,
    build_repair_effectiveness_record,
    build_repair_readiness_candidate,
    build_repair_recurrence_record,
    evaluate_repair_candidate,
    generate_repair_candidate,
)
from spectrum_systems.modules.runtime.ril_interpretation import (
    RILInterpretationError,
    build_ambiguity_signal,
    build_effectiveness_record,
    build_interpretation_bundle,
    build_interpretation_record,
    build_readiness_record,
    detect_contradictions,
    evaluate_interpretation,
    monitor_failure_class_drift,
    normalize_failure_packet,
    validate_control_signal_integrity,
    validate_interpretation_repair_alignment,
    validate_replay,
    validate_required_coverage,
)


def _evidence() -> dict:
    return {
        "artifact_type": "execution_failure_packet",
        "source_artifact_ref": "execution_failure_packet:efp-001",
        "failure_class": "slice_contract_mismatch",
        "owner_surface": "RIL",
        "source_evidence_refs": ["trace:trace-ril-001"],
        "lineage_refs": ["lineage:ril-001"],
        "ambiguity_refs": ["ambiguous_stacktrace"],
        "contradiction_refs": ["trace:conflict-a"],
    }


def _fre_packet() -> dict:
    return {
        "artifact_type": "execution_failure_packet",
        "failure_packet_id": "efp-001",
        "classified_failure_type": "slice_contract_mismatch",
        "affected_artifact_refs": ["contracts/examples/review_control_signal_artifact.json"],
        "trace_refs": ["trace:trace-ril-001"],
        "validation_refs": ["pytest_failure:tests/test_review_roadmap_generator.py::test_requires_nested_control_decision"],
    }


def test_ril_foundation_outputs_schema_valid_artifacts() -> None:
    packet = normalize_failure_packet(evidence=_evidence(), trace_id="trace-ril-001")
    conflict = detect_contradictions(failure_packet=packet, evidence_refs=["trace:conflict-a", "trace:conflict-b"], material_threshold=3)
    interpretation = build_interpretation_record(
        failure_packet=packet,
        conflict_record=conflict,
        interpretation_notes=["bounded normalization complete"],
    )
    evaluation = evaluate_interpretation(interpretation_record=interpretation, conflict_record=conflict)
    readiness = build_readiness_record(interpretation_record=interpretation, eval_result=evaluation)
    bundle = build_interpretation_bundle(
        failure_packet=packet,
        interpretation_record=interpretation,
        eval_result=evaluation,
        readiness_record=readiness,
        conflict_record=conflict,
    )

    for artifact_type, artifact in (
        ("failure_packet", packet),
        ("interpretation_conflict_record", conflict),
        ("interpretation_record", interpretation),
        ("interpretation_eval_result", evaluation),
        ("interpretation_readiness_record", readiness),
        ("interpretation_bundle", bundle),
    ):
        validate_artifact(artifact, artifact_type)


def test_ril_deterministic_replay_and_version_drift_detection() -> None:
    packet = normalize_failure_packet(evidence=_evidence(), trace_id="trace-ril-001")
    replay = validate_replay(
        source_inputs=[_evidence()],
        first_outputs=[packet],
        replay_outputs=[dict(packet)],
        schema_version="1.0.0",
    )
    validate_artifact(replay, "interpretation_replay_validation_record")
    assert replay["deterministic_match"] is True

    drift = validate_replay(
        source_inputs=[_evidence()],
        first_outputs=[packet],
        replay_outputs=[{**packet, "schema_version": "2.0.0"}],
        schema_version="2.0.0",
    )
    assert drift["result"] == "fail"


def test_ril_ambiguity_budget_control_signal_and_coverage_fail_closed() -> None:
    packet = normalize_failure_packet(evidence=_evidence(), trace_id="trace-ril-001")
    conflict = detect_contradictions(failure_packet=packet, evidence_refs=["trace:conflict-a"], material_threshold=2)
    interpretation = build_interpretation_record(
        failure_packet=packet,
        conflict_record=conflict,
        interpretation_notes=["bounded normalization complete"],
    )

    signal = build_ambiguity_signal(interpretation_records=[interpretation], ambiguity_budget=0.2)
    validate_artifact(signal, "interpretation_ambiguity_signal")
    assert signal["freeze_ready"] is True

    control = validate_control_signal_integrity(
        interpretation_record=interpretation,
        allowed_fields=["normalized_failure_class", "reason_code"],
    )
    validate_artifact(control, "interpretation_control_signal_validation")
    assert control["result"] == "pass"

    coverage = validate_required_coverage(
        required_failure_classes=["slice_contract_mismatch", "runtime_logic_defect"],
        covered_failure_classes=["slice_contract_mismatch"],
        fail_closed=True,
    )
    validate_artifact(coverage, "interpretation_coverage_report")
    assert coverage["fail_closed_triggered"] is True


def test_ril_alignment_effectiveness_and_drift_monitor() -> None:
    packet = normalize_failure_packet(evidence=_evidence(), trace_id="trace-ril-001")
    conflict = detect_contradictions(failure_packet=packet, evidence_refs=["trace:conflict-a"], material_threshold=2)
    interpretation = build_interpretation_record(
        failure_packet=packet,
        conflict_record=conflict,
        interpretation_notes=["bounded normalization complete"],
    )

    candidate = generate_repair_candidate(failure_packet=_fre_packet(), trace_id="trace-ril-001")
    alignment = validate_interpretation_repair_alignment(interpretation_record=interpretation, repair_candidate=candidate)
    validate_artifact(alignment, "interpretation_repair_alignment_record")
    assert alignment["alignment_passed"] is True

    effectiveness = build_effectiveness_record(
        interpretation_record=interpretation,
        alignment_record=alignment,
        downstream_outcome="improved",
    )
    validate_artifact(effectiveness, "interpretation_effectiveness_record")
    assert effectiveness["effective"] is True

    drift = monitor_failure_class_drift(
        baseline_distribution={"slice_contract_mismatch": 8},
        observed_distribution={"slice_contract_mismatch": 6, "new_failure_shape": 3},
        novelty_threshold=0.2,
    )
    validate_artifact(drift, "failure_class_drift_record")
    assert drift["drift_detected"] is True


def test_ril_boundary_fencing_rejects_invalid_upstream_artifacts() -> None:
    bad = _evidence()
    bad["artifact_type"] = "repair_candidate"
    try:
        normalize_failure_packet(evidence=bad, trace_id="trace-ril-001")
        raise AssertionError("expected RILInterpretationError")
    except RILInterpretationError as exc:
        assert "upstream boundary" in str(exc)


def test_ril_readiness_blocks_unresolved_material_contradictions() -> None:
    packet = normalize_failure_packet(evidence=_evidence(), trace_id="trace-ril-001")
    conflict = detect_contradictions(failure_packet=packet, evidence_refs=["trace:conflict-a", "trace:conflict-b"], material_threshold=1)
    interpretation = build_interpretation_record(
        failure_packet=packet,
        conflict_record=conflict,
        interpretation_notes=["bounded normalization complete"],
    )
    evaluation = evaluate_interpretation(interpretation_record=interpretation, conflict_record=conflict)
    readiness = build_readiness_record(interpretation_record=interpretation, eval_result=evaluation)
    assert evaluation["result"] == "fail"
    assert readiness["candidate_ready"] is False
    assert "eval_not_pass" in readiness["blocking_reasons"]


def test_alignment_surface_uses_real_fre_outputs() -> None:
    candidate = generate_repair_candidate(failure_packet=_fre_packet(), trace_id="trace-ril-001")
    eval_result = evaluate_repair_candidate(repair_candidate=candidate)
    effectiveness = build_repair_effectiveness_record(repair_candidate=candidate, repair_eval_result=eval_result)
    recurrence = build_repair_recurrence_record(repair_candidate=candidate, recurrence_count=1, cluster_key="slice_contract_mismatch::review")
    readiness = build_repair_readiness_candidate(repair_candidate=candidate, repair_eval_result=eval_result)
    bundle = build_repair_bundle(
        repair_candidate=candidate,
        repair_eval_result=eval_result,
        repair_effectiveness_record=effectiveness,
        repair_recurrence_record=recurrence,
        repair_readiness_candidate=readiness,
    )
    assert bundle["artifact_type"] == "repair_bundle"
