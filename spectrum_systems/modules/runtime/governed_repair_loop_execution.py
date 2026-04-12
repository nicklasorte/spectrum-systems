"""Deterministic governed repair-loop execution and resume orchestration (GRC-INTEGRATION-01).

This module wires the full artifact-driven loop:
failure -> packet -> bounded candidate -> CDE decision -> TPA gate -> PQX execution
-> RQX review + RIL interpretation -> TLC resume.
"""

from __future__ import annotations

import json
import hashlib
import subprocess
import sys
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.governed_repair_foundation import (
    GovernedRepairFoundationError,
    build_bounded_repair_candidate,
    build_cde_repair_continuation_input,
    build_execution_failure_packet,
    build_tpa_repair_gating_input,
    evaluate_slice_artifact_readiness,
)
from spectrum_systems.modules.runtime.failure_diagnosis_engine import (
    build_failure_diagnosis_artifact,
)
from spectrum_systems.modules.runtime.system_enforcement_layer import enforce_preflight_remediation_boundaries
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


def _parse_iso8601(value: str, *, field: str) -> datetime:
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError as exc:  # pragma: no cover - defensive parsing path
        raise GovernedRepairLoopExecutionError(f"{field} must be RFC3339 date-time") from exc


def _canonical_digest(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def run_contract_preflight_production(
    *,
    trace_id: str,
    changed_paths: list[str],
    output_dir: Path | None = None,
    cwd: Path | None = None,
) -> dict[str, Any]:
    """Run the real contract preflight script and return canonical result artifact."""
    root = cwd or Path.cwd()
    out_dir = output_dir or (root / "outputs" / "contract_preflight_remediation" / trace_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    script_rel = "scripts/run_contract_preflight.py"
    command = [sys.executable, script_rel, "--output-dir", str(out_dir)]
    for path in sorted(set(changed_paths)):
        command.extend(["--changed-path", path])
    started_at = _now_iso()
    completed = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
    completed_at = _now_iso()
    artifact_path = out_dir / "contract_preflight_result_artifact.json"
    if completed.returncode not in (0, 2):
        raise GovernedRepairLoopExecutionError(
            f"production contract preflight failed with exit code {completed.returncode}: {completed.stderr.strip()}"
        )
    if not artifact_path.is_file():
        raise GovernedRepairLoopExecutionError("production contract preflight missing contract_preflight_result_artifact.json")
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise GovernedRepairLoopExecutionError("production contract preflight artifact must be an object")
    payload["_execution_record"] = {
        "artifact_type": "preflight_execution_record",
        "owner": "PQX",
        "runner_identity": {"module": "PQX", "script_path": script_rel, "invocation_mode": "production"},
        "trace_id": trace_id,
        "command": command,
        "started_at": started_at,
        "completed_at": completed_at,
        "exit_code": completed.returncode,
        "stdout_digest": hashlib.sha256(completed.stdout.encode("utf-8")).hexdigest(),
        "stderr_digest": hashlib.sha256(completed.stderr.encode("utf-8")).hexdigest(),
        "artifact_path": str(artifact_path),
        "artifact_digest": _canonical_digest(payload),
        "evidence_digest": _canonical_digest([script_rel, command, trace_id, started_at, completed_at, payload]),
        "status": "success" if completed.returncode in (0, 2) else "failed",
    }
    return payload


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
    gating_input_ref = f"tpa_repair_gating_input:{gating_input['gating_input_id']}"
    constraints_missing = not bool(gating_input.get("repair_scope_refs")) or not bool(gating_input.get("allowed_artifact_refs"))
    if constraints_missing:
        return {
            "approved": False,
            "owner": "TPA",
            "reason": "missing_constraints",
            "approved_slice": None,
            "gating_input_ref": gating_input_ref,
        }
    if policy_blocked:
        return {
            "approved": False,
            "owner": "TPA",
            "reason": "policy_blocked",
            "approved_slice": None,
            "gating_input_ref": gating_input_ref,
        }
    if gating_input["retry_budget_remaining"] <= 0:
        return {
            "approved": False,
            "owner": "TPA",
            "reason": "retry_budget_exhausted",
            "approved_slice": None,
            "gating_input_ref": gating_input_ref,
        }
    if gating_input["risk_level"] == "high" and gating_input["complexity_score"] > 3:
        return {
            "approved": False,
            "owner": "TPA",
            "reason": "risk_budget_exceeded",
            "approved_slice": None,
            "gating_input_ref": gating_input_ref,
        }
    approved_slice = {
        "slice_id": f"repair:{gating_input['gating_input_id']}",
        "scope_refs": list(gating_input["repair_scope_refs"]),
        "allowed_artifact_refs": list(gating_input["allowed_artifact_refs"]),
    }
    return {
        "approved": True,
        "owner": "TPA",
        "reason": "approved",
        "approved_slice": approved_slice,
        "gating_input_ref": gating_input_ref,
    }


def _pqx_execute(*, approved_slice: dict[str, Any], trace_id: str, gating_input_ref: str) -> dict[str, Any]:
    for ref in approved_slice["scope_refs"]:
        if ref not in set(approved_slice["allowed_artifact_refs"]):
            raise GovernedRepairLoopExecutionError("PQX attempted to execute outside TPA-approved scope")
    execution_id = deterministic_id(prefix="pser", namespace="grc_pqx_repair_execution", payload=approved_slice)
    return {
        "owner": "PQX",
        "pqx_slice_execution_record": f"pqx_slice_execution_record:{execution_id}",
        "approved_slice_ref": approved_slice["slice_id"],
        "gating_input_ref": gating_input_ref,
        "execution_status": "success",
        "trace_artifacts": [f"trace:{trace_id}:pqx_repair_execution", f"trace:{trace_id}:pqx_scope:{len(approved_slice['scope_refs'])}"],
    }


def _build_canonical_execution_record(
    *,
    trace_id: str,
    run_id: str,
    approved_slice: dict[str, Any],
    gating_input_ref: str,
    decision_ref: str,
) -> dict[str, Any]:
    execution_record_id = deterministic_id(
        prefix="pser",
        namespace="grc_pqx_slice_execution_record",
        payload=[trace_id, run_id, approved_slice["slice_id"], gating_input_ref, decision_ref],
    )
    return {
        "artifact_type": "pqx_slice_execution_record",
        "version": "2.0.0",
        "trace_id": trace_id,
        "run_id": run_id,
        "slice_id": approved_slice["slice_id"],
        "inputs": {
            "scope_refs": list(approved_slice["scope_refs"]),
            "allowed_artifact_refs": list(approved_slice["allowed_artifact_refs"]),
        },
        "outputs": {
            "executed_scope_count": len(approved_slice["scope_refs"]),
            "execution_record_id": execution_record_id,
        },
        "execution_status": "success",
        "timestamps": {"started_at": _now_iso(), "completed_at": _now_iso()},
        "lineage_refs": {
            "failure_packet_ref": approved_slice["scope_refs"][0],
            "repair_candidate_ref": approved_slice["scope_refs"][1],
            "gating_input_ref": gating_input_ref,
            "decision_ref": decision_ref,
        },
        "gating_input_ref": gating_input_ref,
        "decision_ref": decision_ref,
    }


def _rqx_ril_review(*, case: FailureCase, trace_id: str, tmp_dir: Path | None, execution_record_ref: str) -> dict[str, Any]:
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
        "execution_record_ref": execution_record_ref,
        "review_ref": f"review_result_artifact:{deterministic_id(prefix='rqr', namespace='grc_rqx_review', payload=[case.slice_id, repaired])}",
        "interpretation_ref": f"review_integration_packet_artifact:{deterministic_id(prefix='ril', namespace='grc_ril_interpret', payload=[case.slice_id, repaired])}",
        "follow_up_candidate_needed": not repaired,
        "trace_refs": [f"trace:{trace_id}:rqx_review", f"trace:{trace_id}:ril_interpret"],
    }


def _build_canonical_review_result(
    *,
    trace_id: str,
    execution_record_ref: str,
    repaired: bool,
    interpretation_ref: str,
) -> dict[str, Any]:
    outcome = "approved" if repaired else "follow_up_required"
    review_id = deterministic_id(
        prefix="rqr",
        namespace="grc_review_result_artifact",
        payload=[trace_id, execution_record_ref, outcome],
    )
    review = {
        "artifact_type": "review_result_artifact",
        "version": "2.0.0",
        "trace_id": trace_id,
        "execution_record_ref": execution_record_ref,
        "review_outcome": outcome,
        "findings": [],
        "evidence_refs": [execution_record_ref],
        "interpretation_linkage": {"owner": "RIL", "interpretation_ref": interpretation_ref},
        "review_id": review_id,
    }
    if not repaired:
        review["findings"] = [
            {
                "finding_id": "F-1",
                "severity": "high",
                "summary": "Repair validation remained blocked during post-execution review.",
            }
        ]
    return review


def _enforce_artifact_envelope_consistency(
    *,
    trace_id: str,
    packet: dict[str, Any],
    candidate: dict[str, Any],
    continuation_input: dict[str, Any],
    gating_input: dict[str, Any],
    execution_record: dict[str, Any],
    review_result: dict[str, Any],
) -> None:
    if execution_record.get("trace_id") != trace_id or review_result.get("trace_id") != trace_id:
        raise GovernedRepairLoopExecutionError("artifact envelope trace mismatch")
    if execution_record.get("gating_input_ref") != f"tpa_repair_gating_input:{gating_input['gating_input_id']}":
        raise GovernedRepairLoopExecutionError("artifact envelope gating linkage mismatch")
    if execution_record.get("lineage_refs", {}).get("failure_packet_ref") != (
        f"execution_failure_packet:{packet['failure_packet_id']}"
    ):
        raise GovernedRepairLoopExecutionError("artifact envelope failure packet linkage mismatch")
    if execution_record.get("lineage_refs", {}).get("repair_candidate_ref") != (
        f"bounded_repair_candidate_artifact:{candidate['candidate_id']}"
    ):
        raise GovernedRepairLoopExecutionError("artifact envelope repair candidate linkage mismatch")
    if execution_record.get("decision_ref") != f"cde_repair_continuation_input:{continuation_input['continuation_input_id']}":
        raise GovernedRepairLoopExecutionError("artifact envelope decision linkage mismatch")
    if review_result.get("execution_record_ref") != f"pqx_slice_execution_record:{execution_record['outputs']['execution_record_id']}":
        raise GovernedRepairLoopExecutionError("artifact envelope review linkage mismatch")


def _build_resume_record(*, case: FailureCase, trace_id: str, run_id: str, trigger_ref: str) -> dict[str, Any]:
    record = {
        "artifact_type": "resume_record",
        "schema_version": "1.0.0",
        "resume_id": deterministic_id(prefix="resume", namespace="grc_resume", payload=[case.slice_id, trace_id]),
        "checkpoint_id": f"checkpoint:{case.slice_id}",
        "resume_reason": "repair_validated_resume_from_failed_slice",
        "resumed_at": _now_iso(),
        "validation_result": {"status": "valid", "reason_codes": ["RESUME_ALLOWED", "TRACE_CONTINUITY_CONFIRMED"]},
        "trigger_ref": trigger_ref,
        "trace": {"trace_id": trace_id, "agent_run_id": run_id},
    }
    validate_artifact(record, "resume_record")
    return record


def replay_governed_repair_loop_from_artifacts(*, artifacts: dict[str, Any]) -> dict[str, Any]:
    required = {"packet", "candidate", "continuation_input", "gating_input", "execution_record", "review_result", "resume_record"}
    missing = sorted(required - set(artifacts))
    if missing:
        raise GovernedRepairLoopExecutionError(f"replay missing artifacts: {', '.join(missing)}")

    execution = artifacts["execution_record"]
    review = artifacts["review_result"]
    if execution.get("artifact_type") != "pqx_slice_execution_record":
        raise GovernedRepairLoopExecutionError("replay invalid execution artifact_type")
    if review.get("artifact_type") != "review_result_artifact":
        raise GovernedRepairLoopExecutionError("replay invalid review artifact_type")
    if execution.get("trace_id") != review.get("trace_id"):
        raise GovernedRepairLoopExecutionError("replay trace linkage mismatch")
    if review.get("execution_record_ref") != f"pqx_slice_execution_record:{execution['outputs']['execution_record_id']}":
        raise GovernedRepairLoopExecutionError("replay execution linkage mismatch")
    if execution.get("execution_status") != "success":
        return {"status": "blocked", "explanation": "deterministic: execution_status was not success"}
    if review.get("review_outcome") != "approved":
        return {"status": "not_repaired", "explanation": "deterministic: review_outcome requires follow-up"}
    if artifacts["resume_record"].get("trigger_ref") != f"pqx_slice_execution_record:{execution['outputs']['execution_record_id']}":
        raise GovernedRepairLoopExecutionError("replay trigger linkage mismatch")
    return {"status": "resumed", "explanation": "deterministic: canonical artifact chain is complete"}


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
                "continuation_input": continuation_input,
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
                "continuation_input": continuation_input,
                "decision": cde_decision,
                "gating_input": gating_input,
                "gating_decision": tpa_decision,
            },
        }

    execution = _pqx_execute(
        approved_slice=tpa_decision["approved_slice"],
        trace_id=trace_id,
        gating_input_ref=tpa_decision["gating_input_ref"],
    )
    decision_ref = f"cde_repair_continuation_input:{continuation_input['continuation_input_id']}"
    execution_record = _build_canonical_execution_record(
        trace_id=trace_id,
        run_id=run_id,
        approved_slice={
            "slice_id": execution["approved_slice_ref"],
            "scope_refs": [
                f"execution_failure_packet:{packet['failure_packet_id']}",
                f"bounded_repair_candidate_artifact:{candidate['candidate_id']}",
            ],
            "allowed_artifact_refs": list(gating_input["allowed_artifact_refs"]),
        },
        gating_input_ref=tpa_decision["gating_input_ref"],
        decision_ref=decision_ref,
    )
    execution["canonical_artifact"] = execution_record
    execution["pqx_slice_execution_record"] = f"pqx_slice_execution_record:{execution_record['outputs']['execution_record_id']}"
    review = _rqx_ril_review(
        case=case,
        trace_id=trace_id,
        tmp_dir=tmp_dir,
        execution_record_ref=execution["pqx_slice_execution_record"],
    )
    review_result = _build_canonical_review_result(
        trace_id=trace_id,
        execution_record_ref=execution["pqx_slice_execution_record"],
        repaired=review["repaired"],
        interpretation_ref=review["interpretation_ref"],
    )
    review["canonical_artifact"] = review_result
    _enforce_artifact_envelope_consistency(
        trace_id=trace_id,
        packet=packet,
        candidate=candidate,
        continuation_input=continuation_input,
        gating_input=gating_input,
        execution_record=execution_record,
        review_result=review_result,
    )
    if not review["repaired"]:
        return {
            "status": "not_repaired",
            "stop_reason": "follow_up_candidate_required",
            "trace": {
                "failure": readiness,
                "packet": packet,
                "candidate": candidate,
                "continuation_input": continuation_input,
                "decision": cde_decision,
                "gating_input": gating_input,
                "gating_decision": tpa_decision,
                "execution": execution,
                "review": review,
            },
        }

    resume_record = _build_resume_record(
        case=case,
        trace_id=trace_id,
        run_id=run_id,
        trigger_ref=execution["pqx_slice_execution_record"],
    )
    return {
        "status": "resumed",
        "stop_reason": None,
        "trace": {
            "failure": readiness,
            "packet": packet,
            "candidate": candidate,
            "continuation_input": continuation_input,
            "decision": cde_decision,
            "gating_input": gating_input,
            "gating_decision": tpa_decision,
            "execution": execution,
            "review": review,
            "resume": {"owner": "TLC", "resume_record": resume_record},
        },
}


def _normalize_lineage_ref(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GovernedRepairLoopExecutionError(f"{field} must be a non-empty string")
    return value.strip()


def _require_lineage_continuity(*, admission_lineage: dict[str, Any], trace_id: str) -> dict[str, str]:
    if not isinstance(admission_lineage, dict):
        raise GovernedRepairLoopExecutionError("admission_lineage must be an object")
    request_ref = _normalize_lineage_ref(admission_lineage.get("request_ref"), field="admission_lineage.request_ref")
    admission_ref = _normalize_lineage_ref(admission_lineage.get("admission_ref"), field="admission_lineage.admission_ref")
    tlc_handoff_ref = _normalize_lineage_ref(admission_lineage.get("tlc_handoff_ref"), field="admission_lineage.tlc_handoff_ref")
    lineage_trace = _normalize_lineage_ref(admission_lineage.get("trace_id"), field="admission_lineage.trace_id")
    if lineage_trace != trace_id:
        raise GovernedRepairLoopExecutionError("admission lineage trace continuity mismatch")
    return {
        "request_ref": request_ref,
        "admission_ref": admission_ref,
        "tlc_handoff_ref": tlc_handoff_ref,
        "trace_id": lineage_trace,
    }


def _map_preflight_to_failure_class(preflight_artifact: dict[str, Any]) -> str:
    status = str(preflight_artifact.get("preflight_status") or "").strip().lower()
    gate = str(preflight_artifact.get("control_signal", {}).get("strategy_gate_decision") or "").strip().upper()
    if status == "failed":
        return "runtime_logic_defect" if gate in {"BLOCK", "FREEZE"} else "invalid_artifact_shape"
    if status == "skipped":
        return "policy_blocked"
    raise GovernedRepairLoopExecutionError("preflight remediation bridge requires failed or skipped preflight status")


def _build_preflight_readiness_result(
    *,
    preflight_artifact: dict[str, Any],
    trace_id: str,
) -> dict[str, Any]:
    if preflight_artifact.get("artifact_type") != "contract_preflight_result_artifact":
        raise GovernedRepairLoopExecutionError("preflight_artifact must be contract_preflight_result_artifact")
    gate = str(preflight_artifact.get("control_signal", {}).get("strategy_gate_decision") or "").strip().upper()
    if gate not in {"BLOCK", "FREEZE"}:
        raise GovernedRepairLoopExecutionError("preflight bridge only applies to BLOCK/FREEZE strategy gate decision")
    failure_class = _map_preflight_to_failure_class(preflight_artifact)
    impacted_paths = sorted(
        {
            str(path).strip()
            for path in (
                list(preflight_artifact.get("changed_contracts", []))
                + list(preflight_artifact.get("recommended_repair_area", []))
                + list(preflight_artifact.get("impacted_consumers", []))
            )
            if isinstance(path, str) and path.strip()
        }
    )
    if not impacted_paths:
        impacted_paths = ["outputs/contract_preflight/contract_preflight_result_artifact.json"]
    return {
        "artifact_type": "artifact_readiness_result",
        "schema_version": "1.0.0",
        "readiness_id": deterministic_id(
            prefix="arr",
            namespace="preflight_readiness_bridge",
            payload=[trace_id, gate, preflight_artifact.get("generated_at"), impacted_paths],
        ),
        "slice_id": "CONTRACT_PREFLIGHT",
        "owning_system": "RIL",
        "runtime_seam": "contract_preflight_result_artifact_bridge",
        "status": "blocked",
        "blocking_reasons": [
            {
                "failure_class": failure_class,
                "reason": str(preflight_artifact.get("control_signal", {}).get("rationale") or "preflight gate blocked progression"),
                "artifact_refs": impacted_paths,
                "invariant_refs": ["contract_preflight_result_artifact", f"strategy_gate_decision:{gate}"],
            }
        ],
        "checked_artifact_refs": impacted_paths,
        "contract_invariant_refs": ["artifact_first_execution", "fail_closed_behavior", "promotion_requires_certification"],
        "expected_failure_classes": [failure_class],
    }


def _build_ril_detection_artifact(*, failure_packet: dict[str, Any], rerun_preflight: dict[str, Any]) -> dict[str, Any]:
    blocker = str(failure_packet["classified_failure_type"])
    rerun_gate = str(rerun_preflight.get("control_signal", {}).get("strategy_gate_decision") or "UNKNOWN")
    recurrence_surface = sorted(set(failure_packet["affected_artifact_refs"]))
    trace_gap = not bool(failure_packet.get("trace_refs"))
    return {
        "artifact_type": "preflight_remediation_detection_artifact",
        "artifact_class": "observability_non_authoritative",
        "owner": "RIL",
        "detection_id": deterministic_id(
            prefix="rild",
            namespace="preflight_remediation_detection",
            payload=[failure_packet["failure_packet_id"], rerun_preflight.get("generated_at"), rerun_gate],
        ),
        "failure_packet_ref": f"execution_failure_packet:{failure_packet['failure_packet_id']}",
        "blocker_family": blocker,
        "rerun_outcome": {"preflight_status": rerun_preflight.get("preflight_status"), "strategy_gate_decision": rerun_gate},
        "trace_completeness_gap": trace_gap,
        "recurrence_surfaces": recurrence_surface,
        "authority_state": "non_authoritative",
    }


def _build_prg_recommendation_artifact(*, ril_detection_artifact: dict[str, Any]) -> dict[str, Any]:
    recurrence = ril_detection_artifact["recurrence_surfaces"]
    family = ril_detection_artifact["blocker_family"]
    return {
        "artifact_type": "preflight_remediation_recommendation_artifact",
        "artifact_class": "recommendation_non_authoritative",
        "owner": "PRG",
        "recommendation_id": deterministic_id(
            prefix="prgr",
            namespace="preflight_remediation_recommendation",
            payload=[family, recurrence],
        ),
        "evaluation_pattern_report": {
            "pattern_family": family,
            "recurrence_surface_count": len(recurrence),
        },
        "policy_change_candidate": {"candidate_key": f"policy:{family}", "priority": "medium"},
        "slice_contract_update_candidate": {"slice_ref": "slice:CONTRACT_PREFLIGHT", "candidate_paths": recurrence[:3]},
        "program_roadmap_alignment_result": {
            "alignment": "update_recommended",
            "roadmap_ref": "docs/roadmaps/system_roadmap.md",
        },
        "authority_state": "non_authoritative",
    }


def _build_failure_derived_eval_inputs(
    *,
    failure_packet: dict[str, Any],
    historical_failures: list[dict[str, Any]],
) -> dict[str, Any]:
    blocker = str(failure_packet["classified_failure_type"])
    same_class = [
        item for item in historical_failures if isinstance(item, dict) and str(item.get("classified_failure_type")) == blocker
    ]
    recurrence_count = len(same_class) + 1
    should_emit_case = recurrence_count >= 2
    eval_case = None
    if should_emit_case:
        eval_case = {
            "artifact_type": "preflight_failure_eval_case_candidate",
            "owner": "RIL",
            "authority_state": "non_authoritative",
            "eval_case_id": deterministic_id(
                prefix="pfec",
                namespace="preflight_failure_eval_case_candidate",
                payload=[blocker, sorted(failure_packet["affected_artifact_refs"]), recurrence_count],
            ),
            "failure_packet_ref": f"execution_failure_packet:{failure_packet['failure_packet_id']}",
            "failure_class": blocker,
            "recurrence_count": recurrence_count,
            "target_surfaces": sorted(set(failure_packet["affected_artifact_refs"])),
        }
    return {
        "artifact_type": "preflight_failure_eval_generation_artifact",
        "owner": "RIL",
        "authority_state": "non_authoritative",
        "failure_class": blocker,
        "recurrence_count": recurrence_count,
        "eval_case_candidate": eval_case,
        "candidate_ref": f"preflight_failure_eval_case_candidate:{eval_case['eval_case_id']}" if isinstance(eval_case, dict) else None,
    }


def _evaluate_repair_intent(
    *,
    expected_scope: list[str],
    executed_scope: list[str],
) -> dict[str, Any]:
    expected = sorted(set(path for path in expected_scope if isinstance(path, str) and path.strip()))
    executed = sorted(set(path for path in executed_scope if isinstance(path, str) and path.strip()))
    out_of_scope = sorted(set(executed) - set(expected))
    return {
        "artifact_type": "preflight_repair_intent_eval_artifact",
        "owner": "RIL",
        "authority_state": "non_authoritative",
        "intent_preserved": not bool(out_of_scope),
        "expected_scope_refs": expected,
        "executed_scope_refs": executed,
        "intent_violations": out_of_scope,
    }


def _build_consistency_artifact(
    *,
    context_key: str,
    current_outcome_digest: str,
    prior_outcome_digests: list[str],
) -> dict[str, Any]:
    baseline = sorted(set(item for item in prior_outcome_digests if isinstance(item, str) and item.strip()))
    drift_detected = bool(baseline) and any(item != current_outcome_digest for item in baseline)
    return {
        "artifact_type": "preflight_consistency_artifact",
        "owner": "RIL",
        "authority_state": "non_authoritative",
        "context_key": context_key,
        "current_outcome_digest": current_outcome_digest,
        "baseline_outcome_digests": baseline,
        "drift_detected": drift_detected,
    }


def _build_preflight_ops_artifact(
    *,
    failure_packet: dict[str, Any],
    diagnosis: dict[str, Any],
    started_at: datetime,
    rerun_preflight: dict[str, Any],
    retry_budget_remaining: int,
) -> dict[str, Any]:
    latency_seconds = max(0, int((datetime.now(tz=timezone.utc) - started_at).total_seconds()))
    blocker_family = str(failure_packet["classified_failure_type"])
    passed = str(rerun_preflight.get("preflight_status") or "").lower() == "passed"
    return {
        "artifact_type": "preflight_operations_report_artifact",
        "owner": "PRG",
        "authority_state": "non_authoritative",
        "blocker_taxonomy": {
            "blocker_family": blocker_family,
            "diagnosis_ref": f"failure_diagnosis_artifact:{diagnosis['diagnosis_id']}",
        },
        "trend_signals": {
            "blocker_family_counts": {blocker_family: 1},
            "retry_budget_remaining": retry_budget_remaining,
        },
        "latency_metrics": {
            "repair_latency_seconds": latency_seconds,
        },
        "success_metrics": {
            "success_rate_by_blocker_family": {blocker_family: 1.0 if passed else 0.0},
        },
    }


def _classify_terminal_outcome(
    *,
    rerun_preflight: dict[str, Any],
    retry_budget_remaining: int,
    allow_ambiguous_retry: bool = False,
) -> dict[str, Any]:
    status = str(rerun_preflight.get("preflight_status") or "").lower()
    gate = str(rerun_preflight.get("control_signal", {}).get("strategy_gate_decision") or "").upper()
    if status not in {"passed", "failed", "skipped"}:
        return {"owner": "CDE", "terminal_classification": "ambiguous_block", "next_step": "block"}
    if status == "passed" and gate in {"ALLOW", "WARN"}:
        return {"owner": "CDE", "terminal_classification": "pass_continue", "next_step": "continue"}
    if retry_budget_remaining > 0 and gate in {"BLOCK", "FREEZE"} and allow_ambiguous_retry:
        return {"owner": "CDE", "terminal_classification": "bounded_retry_allowed", "next_step": "continue_repair_bounded"}
    if gate in {"BLOCK", "FREEZE"}:
        return {"owner": "CDE", "terminal_classification": "escalate_human_review", "next_step": "stop_escalate"}
    return {"owner": "CDE", "terminal_classification": "block", "next_step": "block"}


def run_preflight_remediation_loop(
    *,
    preflight_artifact: dict[str, Any],
    admission_lineage: dict[str, Any],
    batch_id: str,
    umbrella_id: str,
    run_id: str,
    trace_id: str,
    retry_budget: int,
    complexity_score: int,
    risk_level: str,
    contract_preflight_runner: Callable[[], dict[str, Any]] | None = None,
    allow_ambiguous_retry: bool = False,
    historical_failures: list[dict[str, Any]] | None = None,
    prior_outcome_digests: list[str] | None = None,
) -> dict[str, Any]:
    """Execute the governed preflight remediation loop using canonical repair contracts."""
    if retry_budget < 0:
        raise GovernedRepairLoopExecutionError("retry_budget must be >= 0")
    started_at = datetime.now(tz=timezone.utc)
    lineage = _require_lineage_continuity(admission_lineage=admission_lineage, trace_id=trace_id)
    request_ref = lineage["request_ref"]
    if not request_ref.startswith("normalized_execution_request:"):
        raise GovernedRepairLoopExecutionError("remediation lineage must bind to normalized_execution_request")
    readiness = _build_preflight_readiness_result(preflight_artifact=preflight_artifact, trace_id=trace_id)
    packet = build_execution_failure_packet(
        readiness_result=readiness,
        execution_refs=[lineage["request_ref"]],
        trace_refs=[f"trace:{trace_id}:preflight_bridge"],
        enforcement_refs=[lineage["tlc_handoff_ref"]],
        validation_refs=[lineage["admission_ref"]],
        batch_id=batch_id,
        umbrella_id=umbrella_id,
        roadmap_context_ref="docs/roadmaps/system_roadmap.md",
    )
    diagnosis = build_failure_diagnosis_artifact(
        failure_source_type="contract_preflight",
        source_artifact_refs=[f"execution_failure_packet:{packet['failure_packet_id']}"],
        failure_payload={
            "observed_failure_summary": packet["explanation"],
            "preflight_status": str(preflight_artifact.get("control_signal", {}).get("strategy_gate_decision") or "BLOCK"),
            "missing_control_inputs": list(preflight_artifact.get("recommended_repair_area") or []),
            "invariant_violations": list(packet.get("validation_refs") or []),
        },
        run_id=run_id,
        trace_id=trace_id,
    )
    candidate = build_bounded_repair_candidate(failure_packet=packet)
    failure_eval_inputs = _build_failure_derived_eval_inputs(
        failure_packet=packet,
        historical_failures=historical_failures or [],
    )
    failure_packet_digest = _canonical_digest(packet)
    repair_candidate_digest = _canonical_digest(candidate)
    continuation_input = build_cde_repair_continuation_input(
        failure_packet=packet,
        repair_candidate=candidate,
        issued_at=_now_iso(),
        freshness_window_seconds=1800,
    )
    decision = {
        "owner": "CDE",
        "decision": continuation_input["recommended_continuation"],
        "continuation_input_ref": f"cde_repair_continuation_input:{continuation_input['continuation_input_id']}",
        "evidence_digest": continuation_input["evidence_digest"],
    }
    if decision["decision"] != "continue_repair_bounded":
        return {"status": "stopped", "trace": {"packet": packet, "diagnosis": diagnosis, "candidate": candidate, "decision": decision}}
    retry_budget_remaining = max(retry_budget - 1, 0)
    gating_input = build_tpa_repair_gating_input(
        failure_packet=packet,
        repair_candidate=candidate,
        retry_budget_remaining=retry_budget_remaining,
        complexity_score=complexity_score,
        risk_level=risk_level,
        issued_at=_now_iso(),
        freshness_window_seconds=1800,
    )
    if continuation_input["failure_packet_digest"] != failure_packet_digest or continuation_input["repair_candidate_digest"] != repair_candidate_digest:
        raise GovernedRepairLoopExecutionError("continuation input digest binding mismatch")
    if gating_input["failure_packet_digest"] != failure_packet_digest or gating_input["repair_candidate_digest"] != repair_candidate_digest:
        raise GovernedRepairLoopExecutionError("gating input digest binding mismatch")

    failure_instance_ref = f"execution_failure_packet:{packet['failure_packet_id']}"
    sel_guard = enforce_preflight_remediation_boundaries(
        remediation_context={
            "lineage": lineage,
            "failure_packet": packet,
            "repair_candidate": candidate,
            "continuation_decision": decision,
            "continuation_input": continuation_input,
            "gating_input": gating_input,
            "retry_budget_remaining": retry_budget_remaining,
            "approved_scope_refs": gating_input["repair_scope_refs"],
            "execution_scope_refs": gating_input["repair_scope_refs"],
            "failure_packet_digest": failure_packet_digest,
            "repair_candidate_digest": repair_candidate_digest,
            "failure_instance_ref": failure_instance_ref,
        }
    )
    if sel_guard["enforcement_status"] != "allow":
        return {"status": "blocked", "stop_reason": "sel_block", "trace": {"packet": packet, "candidate": candidate, "sel": sel_guard}}
    changed_paths = sorted(set(gating_input["repair_scope_refs"]))
    if contract_preflight_runner is None:
        rerun_preflight = run_contract_preflight_production(trace_id=trace_id, changed_paths=changed_paths)
    else:
        rerun_preflight = contract_preflight_runner()
    rerun_execution_record = rerun_preflight.get("_execution_record")
    if not isinstance(rerun_execution_record, dict):
        rerun_execution_record = {
            "artifact_type": "preflight_execution_record",
            "owner": "PQX",
            "runner_identity": {"module": "PQX", "script_path": "scripts/run_contract_preflight.py", "invocation_mode": "injected"},
            "trace_id": trace_id,
            "command": ["injected_runner"],
            "started_at": _now_iso(),
            "completed_at": _now_iso(),
            "exit_code": 0,
            "stdout_digest": hashlib.sha256(b"").hexdigest(),
            "stderr_digest": hashlib.sha256(b"").hexdigest(),
            "artifact_path": "injected",
            "artifact_digest": _canonical_digest(rerun_preflight),
            "evidence_digest": _canonical_digest(rerun_preflight),
            "status": "success",
        }
    rerun_artifact = dict(rerun_preflight)
    rerun_artifact.pop("_execution_record", None)
    rerun_result_digest = _canonical_digest(rerun_artifact)
    if rerun_execution_record.get("artifact_digest") != rerun_result_digest:
        raise GovernedRepairLoopExecutionError("rerun execution evidence digest mismatch")
    if rerun_execution_record.get("trace_id") != trace_id:
        raise GovernedRepairLoopExecutionError("rerun execution evidence trace mismatch")
    _parse_iso8601(str(continuation_input["issued_at"]), field="continuation_input.issued_at")
    _parse_iso8601(str(gating_input["issued_at"]), field="gating_input.issued_at")
    _parse_iso8601(str(rerun_execution_record.get("started_at")), field="rerun_execution_record.started_at")

    ril_detection = _build_ril_detection_artifact(failure_packet=packet, rerun_preflight=rerun_preflight)
    ril_detection["detection_flags"] = {
        "stale_artifact_use_detected": False,
        "lineage_mismatch_detected": False,
        "replay_mismatch_detected": False,
        "rerun_inconsistency_detected": False,
        "scope_pressure_detected": False,
    }
    prg_recommendation = _build_prg_recommendation_artifact(ril_detection_artifact=ril_detection)
    prg_recommendation["trend_outputs"] = {
        "blocker_families": [ril_detection["blocker_family"]],
        "stale_artifact_attempts": 0,
        "retry_exhaustion": 1 if retry_budget_remaining <= 0 else 0,
        "promotion_guard_blocks": 0,
    }
    replay_integrity = {
        "artifact_type": "preflight_replay_integrity_comparison_artifact",
        "owner": "RIL",
        "authority_state": "non_authoritative",
        "failure_packet_digest": failure_packet_digest,
        "repair_candidate_digest": repair_candidate_digest,
        "rerun_result_digest": rerun_result_digest,
    }
    intent_eval = _evaluate_repair_intent(
        expected_scope=list(preflight_artifact.get("recommended_repair_area") or []) + list(changed_paths),
        executed_scope=changed_paths,
    )
    consistency = _build_consistency_artifact(
        context_key=f"{packet['classified_failure_type']}:{sorted(packet['affected_artifact_refs'])}",
        current_outcome_digest=rerun_result_digest,
        prior_outcome_digests=prior_outcome_digests or [],
    )
    policy_version = str(preflight_artifact.get("trace", {}).get("policy_version") or "").strip()
    ops_report = _build_preflight_ops_artifact(
        failure_packet=packet,
        diagnosis=diagnosis,
        started_at=started_at,
        rerun_preflight=rerun_preflight,
        retry_budget_remaining=retry_budget_remaining,
    )
    roadmap_inputs = {
        "artifact_type": "preflight_roadmap_input_artifact",
        "owner": "PRG",
        "authority_state": "non_authoritative",
        "source_failure_class": packet["classified_failure_type"],
        "source_refs": [f"execution_failure_packet:{packet['failure_packet_id']}", f"failure_diagnosis_artifact:{diagnosis['diagnosis_id']}"],
    }
    policy_candidate = {
        "artifact_type": "preflight_policy_candidate_artifact",
        "owner": "PRG",
        "authority_state": "non_authoritative",
        "candidate_id": deterministic_id(
            prefix="ppc",
            namespace="preflight_policy_candidate",
            payload=[packet["classified_failure_type"], failure_eval_inputs["recurrence_count"]],
        ),
        "failure_class": packet["classified_failure_type"],
        "recurrence_count": failure_eval_inputs["recurrence_count"],
        "auto_apply": False,
    }
    repair_passed = str(rerun_preflight.get("preflight_status") or "").lower() == "passed"
    trust_signal = {
        "artifact_type": "preflight_trust_signal_artifact",
        "owner": "PRG",
        "authority_state": "non_authoritative",
        "trust_score": 1.0 if repair_passed else 0.4,
        "cost_benefit": {"cost_units": float(len(changed_paths)), "benefit_units": 1.0 if repair_passed else 0.0},
        "autonomy_readiness_score": 0.75 if repair_passed and intent_eval["intent_preserved"] else 0.2,
    }
    terminal = _classify_terminal_outcome(
        rerun_preflight=rerun_preflight,
        retry_budget_remaining=retry_budget_remaining,
        allow_ambiguous_retry=allow_ambiguous_retry,
    )
    fused_signals = {
        "artifact_type": "preflight_signal_fusion_artifact",
        "owner": "RIL",
        "authority_state": "non_authoritative",
        "signals": {
            "consistency_drift_detected": consistency["drift_detected"],
            "intent_preserved": intent_eval["intent_preserved"],
            "terminal_classification": terminal["terminal_classification"],
        },
    }
    escalation_audit = {
        "artifact_type": "preflight_escalation_audit_artifact",
        "owner": "RIL",
        "authority_state": "non_authoritative",
        "escalation_required": terminal["terminal_classification"] in {"ambiguous_block", "escalate_human_review", "block"},
        "override_applied": False,
        "trace_links": [f"execution_failure_packet:{packet['failure_packet_id']}", decision["continuation_input_ref"]],
    }
    promotion_guard = enforce_preflight_remediation_boundaries(
        remediation_context={
            "lineage": lineage,
            "failure_packet": packet,
            "repair_candidate": candidate,
            "continuation_decision": decision,
            "continuation_input": continuation_input,
            "gating_input": gating_input,
            "retry_budget_remaining": retry_budget_remaining,
            "approved_scope_refs": gating_input["repair_scope_refs"],
            "execution_scope_refs": gating_input["repair_scope_refs"],
            "rerun_preflight_result": rerun_preflight,
            "rerun_execution_record": rerun_execution_record,
            "diagnosis_artifact": diagnosis,
            "terminal_classification": terminal,
            "failure_packet_digest": failure_packet_digest,
            "repair_candidate_digest": repair_candidate_digest,
            "failure_instance_ref": failure_instance_ref,
            "rerun_result_digest": rerun_result_digest,
            "consistency_artifact": consistency,
            "intent_eval": intent_eval,
            "policy_version": policy_version,
            "authority_sequence": ["AEX", "TLC", "TPA", "PQX", "SEL"],
            "dependency_chain_refs": [lineage["request_ref"], lineage["admission_ref"], lineage["tlc_handoff_ref"]],
            "expected_dependency_refs": [lineage["request_ref"], lineage["admission_ref"], lineage["tlc_handoff_ref"]],
            "bypass_signals": [],
        }
    )
    return {
        "status": "completed" if terminal["terminal_classification"] == "pass_continue" and promotion_guard["enforcement_status"] == "allow" else "blocked",
        "trace": {
            "lineage": lineage,
            "packet": packet,
            "diagnosis": diagnosis,
            "candidate": candidate,
            "continuation_input": continuation_input,
            "decision": decision,
            "gating_input": gating_input,
            "sel": sel_guard,
            "rerun_preflight_result": rerun_preflight,
            "rerun_execution_record": rerun_execution_record,
            "ril_detection": ril_detection,
            "ril_replay_integrity": replay_integrity,
            "failure_eval_inputs": failure_eval_inputs,
            "consistency": consistency,
            "intent_eval": intent_eval,
            "prg_recommendation": prg_recommendation,
            "ops_report": ops_report,
            "roadmap_inputs": roadmap_inputs,
            "policy_candidate": policy_candidate,
            "trust_signal": trust_signal,
            "fused_signals": fused_signals,
            "escalation_audit": escalation_audit,
            "terminal": terminal,
            "promotion_guard": promotion_guard,
        },
    }


__all__ = [
    "GovernedRepairLoopExecutionError",
    "replay_governed_repair_loop_from_artifacts",
    "run_contract_preflight_production",
    "run_governed_repair_loop",
    "run_preflight_remediation_loop",
]
