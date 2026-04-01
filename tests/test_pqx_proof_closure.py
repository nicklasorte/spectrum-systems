from __future__ import annotations

import json
from pathlib import Path

import pytest

from spectrum_systems.modules.runtime.pqx_proof_closure import (
    PQXProofClosureError,
    build_bundle_certification_record,
    build_execution_closure_record,
    build_hard_gate_falsification_record,
)


def _sequence_state() -> dict:
    return {
        "requested_slice_ids": ["PQX-QUEUE-01", "PQX-QUEUE-02", "PQX-QUEUE-03"],
        "execution_history": [
            {
                "slice_id": "PQX-QUEUE-01",
                "status": "success",
                "slice_execution_record_ref": "PQX-QUEUE-01.record.json",
                "certification_ref": "PQX-QUEUE-01.cert.json",
                "audit_bundle_ref": "PQX-QUEUE-01.audit.json",
            },
            {
                "slice_id": "PQX-QUEUE-02",
                "status": "success",
                "slice_execution_record_ref": "PQX-QUEUE-02.record.json",
                "certification_ref": "PQX-QUEUE-02.cert.json",
                "audit_bundle_ref": "PQX-QUEUE-02.audit.json",
            },
            {
                "slice_id": "PQX-QUEUE-03",
                "status": "success",
                "slice_execution_record_ref": "PQX-QUEUE-03.record.json",
                "certification_ref": "PQX-QUEUE-03.cert.json",
                "audit_bundle_ref": "PQX-QUEUE-03.audit.json",
            },
        ],
        "failure_eval_policy_linkage": {"linked": True, "evidence_refs": ["failure-binding:critical-001"]},
        "policy_consumption_in_transition": {"linked": True, "evidence_refs": ["transition-policy:consumed:critical-001"]},
        "recurrence_prevention_linkage": {"linked": True, "evidence_refs": ["regression-fixture:critical-001"]},
    }


def _conditions(*, judgment_passed: bool = True, replay_passed: bool = True) -> dict:
    return {
        "missing_failure_binding_evidence": {"passed": True, "reason_code": "OK", "explanation": "binding present", "trace_links": ["a"]},
        "missing_policy_consumption_evidence": {"passed": True, "reason_code": "OK", "explanation": "consumption present", "trace_links": ["b"]},
        "missing_policy_caused_behavior_change": {"passed": True, "reason_code": "OK", "explanation": "behavior changed", "trace_links": ["c"]},
        "missing_recurrence_prevention_linkage": {"passed": True, "reason_code": "OK", "explanation": "recurrence linked", "trace_links": ["d"]},
        "missing_calibration_or_lifecycle_enforcement": {"passed": True, "reason_code": "OK", "explanation": "calibrated", "trace_links": ["e"]},
        "replay_inconsistency": {"passed": replay_passed, "reason_code": "REPLAY_MISMATCH" if not replay_passed else "OK", "explanation": "replay checked", "trace_links": ["f"]},
        "trace_gaps": {"passed": True, "reason_code": "OK", "explanation": "trace complete", "trace_links": ["g"]},
        "judgment_omission_required": {"passed": judgment_passed, "reason_code": "JUDGMENT_MISSING" if not judgment_passed else "OK", "explanation": "judgment checked", "trace_links": ["h"]},
    }


def test_rf18_execution_closure_contains_required_chain() -> None:
    record = build_execution_closure_record(
        run_id="run-g3-001",
        trace_id="trace-g3-001",
        sequence_state=_sequence_state(),
        created_at="2026-04-01T10:00:00Z",
    )
    assert record["replay_verification"]["status"] == "verified"
    assert len(record["pqx_execution_records"]) == 3
    assert record["failure_eval_policy_linkage"]["linked"] is True


def test_rf18_missing_linkage_fails_closed() -> None:
    state = _sequence_state()
    state["policy_consumption_in_transition"] = {"linked": False, "evidence_refs": []}
    with pytest.raises(PQXProofClosureError, match="policy_consumption_in_transition"):
        build_execution_closure_record(
            run_id="run-g3-002",
            trace_id="trace-g3-002",
            sequence_state=state,
            created_at="2026-04-01T10:00:00Z",
        )


def test_rf20_falsification_fails_on_missing_calibration_and_judgment() -> None:
    conditions = _conditions(judgment_passed=False)
    conditions["missing_calibration_or_lifecycle_enforcement"] = {
        "passed": False,
        "reason_code": "CALIBRATION_MISSING",
        "explanation": "calibration data missing",
        "trace_links": ["calibration:missing"],
    }
    record = build_hard_gate_falsification_record(
        run_id="run-g4-001",
        trace_id="trace-g4-001",
        created_at="2026-04-01T10:00:00Z",
        condition_inputs=conditions,
        consumed_by={
            "transition_policy": "sequence_transition_policy",
            "promotion_admission": "pqx_n_slice_validation",
            "certification_gating": "pqx_proof_closure",
        },
    )
    assert record["overall_result"] == "fail"
    assert "missing_calibration_or_lifecycle_enforcement" in record["failed_conditions"]
    assert "judgment_omission_required" in record["failed_conditions"]


def test_rf20_falsification_fails_on_replay_mismatch() -> None:
    record = build_hard_gate_falsification_record(
        run_id="run-g4-002",
        trace_id="trace-g4-002",
        created_at="2026-04-01T10:00:00Z",
        condition_inputs=_conditions(replay_passed=False),
        consumed_by={
            "transition_policy": "sequence_transition_policy",
            "promotion_admission": "pqx_n_slice_validation",
            "certification_gating": "pqx_proof_closure",
        },
    )
    assert record["overall_result"] == "fail"
    assert "replay_inconsistency" in record["failed_conditions"]


def test_rf19_certification_passes_with_full_proof(tmp_path: Path) -> None:
    closure = build_execution_closure_record(
        run_id="run-g4-003",
        trace_id="trace-g4-003",
        sequence_state=_sequence_state(),
        created_at="2026-04-01T10:00:00Z",
    )
    closure_path = tmp_path / "closure.json"
    closure_path.write_text(json.dumps(closure), encoding="utf-8")
    falsification = build_hard_gate_falsification_record(
        run_id="run-g4-003",
        trace_id="trace-g4-003",
        created_at="2026-04-01T10:00:00Z",
        condition_inputs=_conditions(),
        consumed_by={
            "transition_policy": "sequence_transition_policy",
            "promotion_admission": "pqx_n_slice_validation",
            "certification_gating": "pqx_proof_closure",
        },
    )
    falsification_path = tmp_path / "falsification.json"
    falsification_path.write_text(json.dumps(falsification), encoding="utf-8")

    record = build_bundle_certification_record(
        bundle_id="BUNDLE-017",
        created_at="2026-04-01T10:00:00Z",
        execution_closure_ref=str(closure_path),
        hard_gate_falsification_ref=str(falsification_path),
        policy_versions_used={
            "transition_policy": "1",
            "promotion_admission": "1",
            "certification_gating": "1",
        },
        decision_trace_lineage=["trace:1", "trace:2"],
        replay_verification_results={"status": "verified", "details": ["ok"]},
        assertions={
            "sequence_correctness": True,
            "eval_completeness": True,
            "control_enforcement_validity": True,
            "lifecycle_calibration_enforcement": True,
            "judgment_enforcement": True,
        },
        supporting_artifacts=[str(closure_path), str(falsification_path)],
    )
    assert record["final_status"] == "certified"


def test_rf19_certification_fails_when_hard_gate_falsification_fails(tmp_path: Path) -> None:
    closure = build_execution_closure_record(
        run_id="run-g4-004",
        trace_id="trace-g4-004",
        sequence_state=_sequence_state(),
        created_at="2026-04-01T10:00:00Z",
    )
    closure_path = tmp_path / "closure.json"
    closure_path.write_text(json.dumps(closure), encoding="utf-8")
    failed_falsification = build_hard_gate_falsification_record(
        run_id="run-g4-004",
        trace_id="trace-g4-004",
        created_at="2026-04-01T10:00:00Z",
        condition_inputs=_conditions(replay_passed=False),
        consumed_by={
            "transition_policy": "sequence_transition_policy",
            "promotion_admission": "pqx_n_slice_validation",
            "certification_gating": "pqx_proof_closure",
        },
    )
    failed_falsification_path = tmp_path / "failed_falsification.json"
    failed_falsification_path.write_text(json.dumps(failed_falsification), encoding="utf-8")

    with pytest.raises(PQXProofClosureError, match="hard gate falsification"):
        build_bundle_certification_record(
            bundle_id="BUNDLE-017",
            created_at="2026-04-01T10:00:00Z",
            execution_closure_ref=str(closure_path),
            hard_gate_falsification_ref=str(failed_falsification_path),
            policy_versions_used={
                "transition_policy": "1",
                "promotion_admission": "1",
                "certification_gating": "1",
            },
            decision_trace_lineage=["trace:1", "trace:2"],
            replay_verification_results={"status": "verified", "details": ["ok"]},
            assertions={
                "sequence_correctness": True,
                "eval_completeness": True,
                "control_enforcement_validity": True,
                "lifecycle_calibration_enforcement": True,
                "judgment_enforcement": True,
            },
            supporting_artifacts=[str(closure_path), str(failed_falsification_path)],
        )
