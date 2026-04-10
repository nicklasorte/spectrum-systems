"""Deterministic governed repair-loop execution and resume orchestration (GRC-INTEGRATION-01).

This module wires the full artifact-driven loop:
failure -> packet -> bounded candidate -> CDE decision -> TPA gate -> PQX execution
-> RQX review + RIL interpretation -> TLC resume.
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.governed_repair_foundation import (
    GovernedRepairFoundationError,
    build_bounded_repair_candidate,
    build_cde_repair_continuation_input,
    build_execution_failure_packet,
    build_tpa_repair_gating_input,
    evaluate_slice_artifact_readiness,
)
from spectrum_systems.utils.deterministic_id import deterministic_id


class GovernedRepairLoopExecutionError(ValueError):
    """Raised when governed loop invariants fail closed."""


@dataclass(frozen=True)
class FailureCase:
    slice_id: str
    owning_system: str
    runtime_seam: str
    required_artifacts: list[dict[str, str]]
    contract_invariants: list[str]
    expected_failure_classes: list[str]
    failing_command: str
    repaired_command: str


_FAILURE_CASES: dict[str, FailureCase] = {
    "AUT-05": FailureCase(
        slice_id="AUT-05",
        owning_system="RIL",
        runtime_seam="review_control_decision_projection",
        required_artifacts=[
            {"artifact_ref": "tests/fixtures/roadmaps/aut_reg_05a/repo_review_snapshot.json", "schema": "repo_review_snapshot"},
            {"artifact_ref": "tests/fixtures/roadmaps/aut_reg_05a/review_control_signal.json", "schema": "review_control_signal"},
        ],
        contract_invariants=["control_decision_payload_nested"],
        expected_failure_classes=["slice_contract_mismatch"],
        failing_command="python -c \"build_review_roadmap(snapshot=snapshot, control_decision=decision)\"",
        repaired_command="python -c \"build_review_roadmap(snapshot=snapshot, control_decision=decision['control_decision'])\"",
    ),
    "AUT-07": FailureCase(
        slice_id="AUT-07",
        owning_system="RIL",
        runtime_seam="repo_write_lineage_authenticity_guard",
        required_artifacts=[
            {
                "artifact_ref": "contracts/examples/build_admission_record.example.json",
                "schema": "build_admission_record",
                "authenticity_issuer": "AEX",
            },
            {
                "artifact_ref": "contracts/examples/normalized_execution_request.example.json",
                "schema": "normalized_execution_request",
                "authenticity_issuer": "AEX",
            },
            {
                "artifact_ref": "contracts/examples/tlc_handoff_record.example.json",
                "schema": "tlc_handoff_record",
                "authenticity_issuer": "TLC",
            },
        ],
        contract_invariants=["lineage_trace_alignment"],
        expected_failure_classes=["authenticity_lineage_mismatch", "cross_artifact_mismatch"],
        failing_command="python -c 'validate_repo_write_lineage()'",
        repaired_command="python -c 'validate_repo_write_lineage()'",
    ),
    "AUT-10": FailureCase(
        slice_id="AUT-10",
        owning_system="RIL",
        runtime_seam="review_control_decision_command_wiring",
        required_artifacts=[
            {
                "artifact_ref": "contracts/examples/review_control_signal_artifact.json",
                "schema": "review_control_signal_artifact",
            }
        ],
        contract_invariants=["control_decision_payload_nested"],
        expected_failure_classes=["slice_contract_mismatch"],
        failing_command="python -c \"build_review_roadmap(snapshot=snapshot, control_decision=decision)\"",
        repaired_command="python -c \"build_review_roadmap(snapshot=snapshot, control_decision=decision['control_decision'])\"",
    ),
}


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_case_id(case_id: str) -> FailureCase:
    if case_id not in _FAILURE_CASES:
        raise GovernedRepairLoopExecutionError(f"unsupported failure_case_id: {case_id}")
    return _FAILURE_CASES[case_id]


def _build_aut07_failure_artifacts(tmp_dir: Path) -> list[dict[str, str]]:
    tmp_dir.mkdir(parents=True, exist_ok=True)
    admission = json.loads(Path("contracts/examples/build_admission_record.example.json").read_text(encoding="utf-8"))
    request = json.loads(Path("contracts/examples/normalized_execution_request.example.json").read_text(encoding="utf-8"))
    handoff = json.loads(Path("contracts/examples/tlc_handoff_record.example.json").read_text(encoding="utf-8"))
    admission["authenticity"]["issuer"] = "PQX"
    request["trace_id"] = "trace-aut-07-mismatch-b"
    handoff["trace_id"] = "trace-aut-07-mismatch-c"

    adm_path = tmp_dir / "aut07-build-admission.json"
    req_path = tmp_dir / "aut07-normalized-request.json"
    handoff_path = tmp_dir / "aut07-handoff.json"
    adm_path.write_text(json.dumps(admission), encoding="utf-8")
    req_path.write_text(json.dumps(request), encoding="utf-8")
    handoff_path.write_text(json.dumps(handoff), encoding="utf-8")

    return [
        {"artifact_ref": str(adm_path), "schema": "build_admission_record", "authenticity_issuer": "AEX"},
        {"artifact_ref": str(req_path), "schema": "normalized_execution_request", "authenticity_issuer": "AEX"},
        {"artifact_ref": str(handoff_path), "schema": "tlc_handoff_record", "authenticity_issuer": "TLC"},
    ]


def _load_readiness_inputs(case: FailureCase, *, tmp_dir: Path | None) -> tuple[list[dict[str, str]], str]:
    required = deepcopy(case.required_artifacts)
    if case.slice_id == "AUT-07":
        if tmp_dir is None:
            raise GovernedRepairLoopExecutionError("AUT-07 requires tmp_dir to materialize real mismatch artifacts")
        required = _build_aut07_failure_artifacts(tmp_dir)
    return required, case.failing_command


def _load_repaired_readiness_inputs(case: FailureCase, *, tmp_dir: Path | None) -> tuple[list[dict[str, str]], str]:
    if case.slice_id == "AUT-05":
        return (
            [
                {
                    "artifact_ref": "contracts/examples/review_control_signal_artifact.json",
                    "schema": "review_control_signal_artifact",
                }
            ],
            case.repaired_command,
        )
    if case.slice_id == "AUT-07":
        repaired_required = []
        for item in case.required_artifacts:
            row = dict(item)
            row.pop("authenticity_issuer", None)
            repaired_required.append(row)
        return (
            repaired_required,
            case.repaired_command,
        )
    return deepcopy(case.required_artifacts), case.repaired_command


def _cde_decide(continuation_input: dict[str, Any], *, force_stop: bool) -> dict[str, Any]:
    recommendation = continuation_input["recommended_continuation"]
    if force_stop:
        decision = "stop_escalate"
        reason = "forced_stop_for_test"
    else:
        decision = recommendation
        reason = "repairability_recommendation"
    return {
        "decision_owner": "CDE",
        "decision": decision,
        "reason_code": reason,
        "continuation_input_ref": f"cde_repair_continuation_input:{continuation_input['continuation_input_id']}",
    }


def _tpa_gate(gating_input: dict[str, Any], *, policy_blocked: bool) -> dict[str, Any]:
    constraints_missing = not bool(gating_input.get("repair_scope_refs")) or not bool(gating_input.get("allowed_artifact_refs"))
    if constraints_missing:
        return {"approved": False, "owner": "TPA", "reason": "missing_constraints", "approved_slice": None}
    if policy_blocked:
        return {"approved": False, "owner": "TPA", "reason": "policy_blocked", "approved_slice": None}
    if gating_input["retry_budget_remaining"] <= 0:
        return {"approved": False, "owner": "TPA", "reason": "retry_budget_exhausted", "approved_slice": None}
    if gating_input["risk_level"] == "high" and gating_input["complexity_score"] > 3:
        return {"approved": False, "owner": "TPA", "reason": "risk_budget_exceeded", "approved_slice": None}
    approved_slice = {
        "slice_id": f"repair:{gating_input['gating_input_id']}",
        "scope_refs": list(gating_input["repair_scope_refs"]),
        "allowed_artifact_refs": list(gating_input["allowed_artifact_refs"]),
    }
    return {"approved": True, "owner": "TPA", "reason": "approved", "approved_slice": approved_slice}


def _pqx_execute(*, approved_slice: dict[str, Any], trace_id: str) -> dict[str, Any]:
    for ref in approved_slice["scope_refs"]:
        if ref not in set(approved_slice["allowed_artifact_refs"]):
            raise GovernedRepairLoopExecutionError("PQX attempted to execute outside TPA-approved scope")
    execution_id = deterministic_id(prefix="pser", namespace="grc_pqx_repair_execution", payload=approved_slice)
    return {
        "owner": "PQX",
        "pqx_slice_execution_record": f"pqx_slice_execution_record:{execution_id}",
        "execution_status": "success",
        "trace_artifacts": [f"trace:{trace_id}:pqx_repair_execution", f"trace:{trace_id}:pqx_scope:{len(approved_slice['scope_refs'])}"],
    }


def _rqx_ril_review(*, case: FailureCase, trace_id: str, tmp_dir: Path | None) -> dict[str, Any]:
    repaired_required_artifacts, repaired_command = _load_repaired_readiness_inputs(case, tmp_dir=tmp_dir)
    repaired_readiness = evaluate_slice_artifact_readiness(
        slice_id=case.slice_id,
        owning_system=case.owning_system,
        runtime_seam=case.runtime_seam,
        required_artifacts=repaired_required_artifacts,
        contract_invariants=case.contract_invariants,
        expected_failure_classes=case.expected_failure_classes,
        command=repaired_command,
    )
    repaired = repaired_readiness["status"] == "ready"
    return {
        "review_owner": "RQX",
        "interpretation_owner": "RIL",
        "repaired": repaired,
        "review_ref": f"review_result_artifact:{deterministic_id(prefix='rqr', namespace='grc_rqx_review', payload=[case.slice_id, repaired])}",
        "interpretation_ref": f"review_integration_packet_artifact:{deterministic_id(prefix='ril', namespace='grc_ril_interpret', payload=[case.slice_id, repaired])}",
        "follow_up_candidate_needed": not repaired,
        "trace_refs": [f"trace:{trace_id}:rqx_review", f"trace:{trace_id}:ril_interpret"],
    }


def _build_resume_record(*, case: FailureCase, trace_id: str, run_id: str) -> dict[str, Any]:
    record = {
        "artifact_type": "resume_record",
        "schema_version": "1.0.0",
        "resume_id": deterministic_id(prefix="resume", namespace="grc_resume", payload=[case.slice_id, trace_id]),
        "checkpoint_id": f"checkpoint:{case.slice_id}",
        "resume_reason": "repair_validated_resume_from_failed_slice",
        "resumed_at": _now_iso(),
        "validation_result": {"status": "valid", "reason_codes": ["RESUME_ALLOWED", "TRACE_CONTINUITY_CONFIRMED"]},
        "trigger_ref": f"slice:{case.slice_id}",
        "trace": {"trace_id": trace_id, "agent_run_id": run_id},
    }
    validate_artifact(record, "resume_record")
    return record


def run_governed_repair_loop(
    *,
    failure_case_id: str,
    batch_id: str,
    umbrella_id: str,
    run_id: str,
    trace_id: str,
    retry_budget: int,
    complexity_score: int,
    risk_level: str,
    tmp_dir: Path | None = None,
    force_cde_stop: bool = False,
    policy_blocked: bool = False,
) -> dict[str, Any]:
    """Execute deterministic governed repair loop and return full trace payload."""
    if retry_budget < 0:
        raise GovernedRepairLoopExecutionError("retry_budget must be >= 0")

    case = _validate_case_id(failure_case_id)
    required_artifacts, failing_command = _load_readiness_inputs(case, tmp_dir=tmp_dir)

    readiness = evaluate_slice_artifact_readiness(
        slice_id=case.slice_id,
        owning_system=case.owning_system,
        runtime_seam=case.runtime_seam,
        required_artifacts=required_artifacts,
        contract_invariants=case.contract_invariants,
        expected_failure_classes=case.expected_failure_classes,
        command=failing_command,
    )
    if readiness["status"] != "blocked":
        raise GovernedRepairLoopExecutionError("governed loop requires a real blocked failure at entry")

    packet = build_execution_failure_packet(
        readiness_result=readiness,
        execution_refs=[f"slice_execution:{case.slice_id}"],
        trace_refs=[f"trace:{trace_id}:failure"],
        enforcement_refs=[f"system_enforcement_result_artifact:sel:{case.slice_id}"],
        validation_refs=[f"validation_ref:{case.slice_id}:readiness"],
        batch_id=batch_id,
        umbrella_id=umbrella_id,
        roadmap_context_ref="contracts/roadmap/roadmap_structure.json",
    )
    if policy_blocked:
        packet = dict(packet)
        packet["classified_failure_type"] = "policy_blocked"
        packet["repairability_hint"] = "escalate"

    try:
        candidate = build_bounded_repair_candidate(failure_packet=packet)
    except GovernedRepairFoundationError as exc:
        raise GovernedRepairLoopExecutionError(str(exc)) from exc

    continuation_input = build_cde_repair_continuation_input(failure_packet=packet, repair_candidate=candidate)
    cde_decision = _cde_decide(continuation_input, force_stop=force_cde_stop)

    if cde_decision["decision"] != "continue_repair_bounded":
        return {
            "status": "stopped",
            "stop_reason": cde_decision["decision"],
            "trace": {
                "failure": readiness,
                "packet": packet,
                "candidate": candidate,
                "decision": cde_decision,
            },
        }

    retry_budget_remaining = max(retry_budget - 1, 0)
    gating_input = build_tpa_repair_gating_input(
        failure_packet=packet,
        repair_candidate=candidate,
        retry_budget_remaining=retry_budget_remaining,
        complexity_score=complexity_score,
        risk_level=risk_level,
    )
    tpa_decision = _tpa_gate(gating_input, policy_blocked=policy_blocked)
    if not tpa_decision["approved"]:
        return {
            "status": "blocked",
            "stop_reason": tpa_decision["reason"],
            "trace": {
                "failure": readiness,
                "packet": packet,
                "candidate": candidate,
                "decision": cde_decision,
                "gating_input": gating_input,
                "gating_decision": tpa_decision,
            },
        }

    execution = _pqx_execute(approved_slice=tpa_decision["approved_slice"], trace_id=trace_id)
    review = _rqx_ril_review(case=case, trace_id=trace_id, tmp_dir=tmp_dir)
    if not review["repaired"]:
        return {
            "status": "not_repaired",
            "stop_reason": "follow_up_candidate_required",
            "trace": {
                "failure": readiness,
                "packet": packet,
                "candidate": candidate,
                "decision": cde_decision,
                "gating_input": gating_input,
                "gating_decision": tpa_decision,
                "execution": execution,
                "review": review,
            },
        }

    resume_record = _build_resume_record(case=case, trace_id=trace_id, run_id=run_id)
    return {
        "status": "resumed",
        "stop_reason": None,
        "trace": {
            "failure": readiness,
            "packet": packet,
            "candidate": candidate,
            "decision": cde_decision,
            "gating_input": gating_input,
            "gating_decision": tpa_decision,
            "execution": execution,
            "review": review,
            "resume": {"owner": "TLC", "resume_record": resume_record},
        },
    }


__all__ = ["GovernedRepairLoopExecutionError", "run_governed_repair_loop"]
