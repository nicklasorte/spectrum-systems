from __future__ import annotations

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.fre_repair_flow import (
    FRERepairFlowError,
    build_repair_bundle,
    build_repair_effectiveness_record,
    build_repair_readiness_candidate,
    build_repair_recurrence_record,
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
    assert first["candidate_id"].startswith("fre-rc-")
    validate_artifact(first, "repair_candidate")


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


def test_repair_bundle_wires_all_fre_records() -> None:
    candidate = generate_repair_candidate(failure_packet=_packet(), trace_id="trace-fre-001")
    result = evaluate_repair_candidate(repair_candidate=candidate)
    eff = build_repair_effectiveness_record(repair_candidate=candidate, repair_eval_result=result)
    rec = build_repair_recurrence_record(repair_candidate=candidate, recurrence_count=0)
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
