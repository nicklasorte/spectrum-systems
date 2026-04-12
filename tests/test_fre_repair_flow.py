from __future__ import annotations

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.fre_repair_flow import (
    FRERepairFlowError,
    apply_repair_scope_policy_gate,
    build_fre_promotion_gate_record,
    build_override_record,
    build_repair_budget_signal,
    build_repair_bundle,
    build_repair_effectiveness_record,
    build_repair_judgment_slice,
    build_repair_readiness_candidate,
    build_repair_recurrence_record,
    build_repair_template_candidate,
    build_review_record,
    compile_repair_policy_candidate,
    evaluate_repair_candidate,
    generate_repair_candidate,
)


def _packet() -> dict:
    return {
        "artifact_type": "execution_failure_packet",
        "failure_packet_id": "efp-001",
        "classified_failure_type": "slice_contract_mismatch",
        "affected_artifact_refs": ["contracts/examples/review_control_signal_artifact.json"],
        "trace_refs": ["trace:trace-fre-001"],
        "validation_refs": ["pytest_failure:tests/test_review_roadmap_generator.py::test_requires_nested_control_decision"],
    }


def test_generate_repair_candidate_is_deterministic_and_schema_valid() -> None:
    first = generate_repair_candidate(failure_packet=_packet(), trace_id="trace-fre-001")
    second = generate_repair_candidate(failure_packet=_packet(), trace_id="trace-fre-001")
    assert first == second
    validate_artifact(first, "repair_candidate")
    assert first["non_authority_assertions"]


def test_upstream_fencing_blocks_non_failure_packet_inputs() -> None:
    bad = dict(_packet())
    bad["artifact_type"] = "repair_candidate"
    try:
        generate_repair_candidate(failure_packet=bad, trace_id="trace-fre-001")
        raise AssertionError("expected FRERepairFlowError")
    except FRERepairFlowError as exc:
        assert "execution_failure_packet" in str(exc)


def test_repair_eval_harness_fails_closed_for_non_replay_compatible_candidate() -> None:
    candidate = generate_repair_candidate(failure_packet=_packet(), trace_id="trace-fre-001")
    result = evaluate_repair_candidate(repair_candidate=candidate, replay_compatible=False)
    validate_artifact(result, "repair_eval_result")
    assert result["result"] == "fail"
    assert "replay_provenance_incompatible" in result["fail_reasons"]


def test_readiness_candidate_is_non_authoritative_and_blocks_failed_eval() -> None:
    candidate = generate_repair_candidate(failure_packet=_packet(), trace_id="trace-fre-001")
    failed_eval = evaluate_repair_candidate(repair_candidate=candidate, replay_compatible=False)
    readiness = build_repair_readiness_candidate(repair_candidate=candidate, repair_eval_result=failed_eval)
    validate_artifact(readiness, "repair_readiness_candidate")
    assert readiness["candidate_ready"] is False
    assert "cannot_authorize_execution" in readiness["non_authority_assertions"]


def test_repair_bundle_wires_all_fre_records_and_replay_binding() -> None:
    candidate = generate_repair_candidate(failure_packet=_packet(), trace_id="trace-fre-001")
    result = evaluate_repair_candidate(repair_candidate=candidate)
    eff = build_repair_effectiveness_record(repair_candidate=candidate, repair_eval_result=result)
    rec = build_repair_recurrence_record(repair_candidate=candidate, recurrence_count=2, cluster_key="slice_contract_mismatch::review")
    ready = build_repair_readiness_candidate(repair_candidate=candidate, repair_eval_result=result)
    bundle = build_repair_bundle(
        repair_candidate=candidate,
        repair_eval_result=result,
        repair_effectiveness_record=eff,
        repair_recurrence_record=rec,
        repair_readiness_candidate=ready,
    )
    validate_artifact(eff, "repair_effectiveness_record")
    validate_artifact(rec, "repair_recurrence_record")
    validate_artifact(bundle, "repair_bundle")


def test_template_admission_policy_gate_review_override_and_metrics() -> None:
    candidate = generate_repair_candidate(failure_packet=_packet(), trace_id="trace-fre-001")
    result = evaluate_repair_candidate(repair_candidate=candidate)
    eff = build_repair_effectiveness_record(repair_candidate=candidate, repair_eval_result=result)
    eff2 = dict(eff)
    eff2["repair_candidate_ref"] = "repair_candidate:fre-rc-fedcba9876543210"
    template = build_repair_template_candidate(cluster_key="slice_contract_mismatch::review", successful_records=[eff, eff2], min_successes=2)
    validate_artifact(template, "repair_template_candidate")

    gate = apply_repair_scope_policy_gate(
        repair_candidate=candidate,
        policy={
            "allowed_classes": ["artifact_only"],
            "blocked_classes": ["runtime_code"],
            "review_required_classes": ["schema_adjustment"],
        },
    )
    validate_artifact(gate, "repair_scope_policy_gate")
    assert gate["decision"] == "allowed"

    review = build_review_record(
        repair_candidate=candidate,
        reviewer_id="rev-1",
        disposition="approved",
        notes="bounded and replay-safe",
    )
    validate_artifact(review, "repair_review_record")
    override = build_override_record(
        review_record=review,
        override_by="operator-1",
        expires_at="2026-04-20T00:00:00Z",
        justification="time-bound override for sequencing",
    )
    validate_artifact(override, "repair_override_record")

    signal = build_repair_budget_signal(
        effectiveness_records=[eff],
        recurrence_records=[build_repair_recurrence_record(repair_candidate=candidate, recurrence_count=3, cluster_key="slice_contract_mismatch::review")],
        override_records=[override],
        total_latency_ms=250,
        total_cost_units=2,
    )
    validate_artifact(signal, "repair_budget_signal")
    assert signal["override_rate"] == 1.0


def test_judgment_policy_candidate_and_promotion_gate() -> None:
    candidate = generate_repair_candidate(failure_packet=_packet(), trace_id="trace-fre-001")
    result = evaluate_repair_candidate(repair_candidate=candidate)
    eff = build_repair_effectiveness_record(repair_candidate=candidate, repair_eval_result=result)
    rec = build_repair_recurrence_record(repair_candidate=candidate, recurrence_count=1, cluster_key="slice_contract_mismatch::review")
    ready = build_repair_readiness_candidate(repair_candidate=candidate, repair_eval_result=result)
    bundle = build_repair_bundle(
        repair_candidate=candidate,
        repair_eval_result=result,
        repair_effectiveness_record=eff,
        repair_recurrence_record=rec,
        repair_readiness_candidate=ready,
    )

    judgment = build_repair_judgment_slice(
        candidate_scores={f"repair_candidate:{candidate['candidate_id']}": 0.9},
        eval_refs={f"repair_candidate:{candidate['candidate_id']}": f"repair_eval_result:{result['eval_id']}"},
        trace_id="trace-fre-001",
    )
    validate_artifact(judgment, "repair_judgment_slice")

    eff2 = dict(eff)
    eff2["repair_candidate_ref"] = "repair_candidate:fre-rc-fedcba9876543210"
    template = build_repair_template_candidate(cluster_key="slice_contract_mismatch::review", successful_records=[eff, eff2], min_successes=2)
    policy_candidate = compile_repair_policy_candidate(templates=[template], min_templates=1)
    validate_artifact(policy_candidate, "repair_policy_candidate")

    gate = apply_repair_scope_policy_gate(
        repair_candidate=candidate,
        policy={"allowed_classes": ["artifact_only"], "blocked_classes": [], "review_required_classes": []},
    )
    signal = build_repair_budget_signal(
        effectiveness_records=[eff],
        recurrence_records=[rec],
        override_records=[],
        total_latency_ms=100,
        total_cost_units=1,
    )
    promotion = build_fre_promotion_gate_record(bundle=bundle, budget_signal=signal, policy_gate=gate, judgment_slice=judgment)
    validate_artifact(promotion, "fre_promotion_gate_record")
    assert promotion["promotion_ready"] is True


def test_policy_gate_fail_closed_and_template_admission_fail_closed() -> None:
    candidate = generate_repair_candidate(failure_packet=_packet(), trace_id="trace-fre-001")
    try:
        apply_repair_scope_policy_gate(repair_candidate=candidate, policy={"allowed_classes": [], "blocked_classes": [], "review_required_classes": []})
        raise AssertionError("expected FRERepairFlowError")
    except FRERepairFlowError as exc:
        assert "fail-closed" in str(exc)

    result = evaluate_repair_candidate(repair_candidate=candidate)
    ineffective = build_repair_effectiveness_record(repair_candidate=candidate, repair_eval_result=result, observed_outcome="unresolved")
    try:
        build_repair_template_candidate(cluster_key="x", successful_records=[ineffective], min_successes=2)
        raise AssertionError("expected FRERepairFlowError")
    except FRERepairFlowError as exc:
        assert "insufficient" in str(exc)
