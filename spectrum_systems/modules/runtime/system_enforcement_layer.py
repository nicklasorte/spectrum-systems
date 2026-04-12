"""System Enforcement Layer (SEL-001): explicit fail-closed governed boundary enforcement."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from jsonschema import Draft202012Validator

from spectrum_systems.contracts import load_schema, validate_artifact
from spectrum_systems.modules.runtime.pqx_execution_authority import (
    PqxExecutionAuthorityError,
    validate_pqx_execution_authority_record,
)

ViolationCode = str

VIOLATION_CODES: tuple[ViolationCode, ...] = (
    "pqx_entry_violation",
    "missing_artifact_violation",
    "tpa_boundary_violation",
    "fre_boundary_violation",
    "ril_boundary_violation",
    "governance_evidence_violation",
    "lineage_violation",
    "repair_scope_violation",
    "repair_budget_violation",
    "repair_decision_violation",
    "failure_class_registry_violation",
    "eval_adoption_violation",
    "roadmap_signal_linkage_violation",
)

_ALLOWED_RIL_INTAKE_TYPES = {
    "review_projection_bundle_artifact",
    "roadmap_review_projection_artifact",
    "control_loop_review_intake_artifact",
    "readiness_review_projection_artifact",
    "ril_04_projection",
}

_REJECTED_RIL_INTAKE_TYPES = {
    "raw_review_markdown",
    "review_signal_artifact",
    "review_control_signal_artifact",
    "integration_packet",
}

_REQUIRED_CORE_ARTIFACT_KEYS = (
    "execution_artifact",
    "trace_refs",
    "lineage",
)


class SystemEnforcementLayerError(ValueError):
    """Raised when SEL inputs or outputs are malformed."""


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash16(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()[:16]


def _normalize_context(context: dict[str, Any]) -> dict[str, Any]:
    execution_request = context.get("execution_request") if isinstance(context.get("execution_request"), dict) else {}
    artifact_references = context.get("artifact_references") if isinstance(context.get("artifact_references"), dict) else {}
    governance_evidence = context.get("governance_evidence") if isinstance(context.get("governance_evidence"), dict) else {}
    downstream_consumption = context.get("downstream_consumption") if isinstance(context.get("downstream_consumption"), dict) else {}

    trace_refs = context.get("trace_refs", artifact_references.get("trace_refs", []))
    if not isinstance(trace_refs, list):
        trace_refs = []

    lineage = context.get("lineage", artifact_references.get("lineage", {}))
    if not isinstance(lineage, dict):
        lineage = {}

    return {
        "execution_request": execution_request,
        "artifact_references": artifact_references,
        "governance_evidence": governance_evidence,
        "downstream_consumption": downstream_consumption,
        "trace_refs": trace_refs,
        "lineage": lineage,
        "source_module": str(context.get("source_module") or "unknown"),
        "caller_identity": str(context.get("caller_identity") or "unknown"),
        "emitted_at": str(
            context.get("emitted_at")
            or execution_request.get("requested_at")
            or "1970-01-01T00:00:00Z"
        ),
    }


def _add_violation(
    violations: list[dict[str, Any]],
    *,
    code: ViolationCode,
    boundary: str,
    field: str,
    message: str,
) -> None:
    violations.append(
        {
            "violation_code": code,
            "boundary": boundary,
            "field": field,
            "message": message,
        }
    )


def _is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return True


def _check_pqx_entry(normalized: dict[str, Any], violations: list[dict[str, Any]]) -> None:
    request = normalized["execution_request"]
    refs = normalized["artifact_references"]
    execution_context = str(request.get("execution_context") or "").strip()
    pqx_entry = bool(request.get("pqx_entry")) or execution_context == "pqx_governed"
    direct_cli = bool(request.get("direct_cli"))
    ad_hoc_runtime = bool(request.get("ad_hoc_runtime"))
    direct_slice_execution = bool(request.get("direct_slice_execution"))

    if not pqx_entry or direct_cli or ad_hoc_runtime or direct_slice_execution:
        _add_violation(
            violations,
            code="pqx_entry_violation",
            boundary="PQX",
            field="execution_request",
            message="execution must originate from PQX-governed flow without direct bypass paths",
        )
        return

    proof = refs.get("pqx_execution_authority_record")
    if not isinstance(proof, dict):
        _add_violation(
            violations,
            code="pqx_entry_violation",
            boundary="PQX",
            field="artifact_references.pqx_execution_authority_record",
            message="PQX-governed execution requires a valid PQX-issued authority proof artifact",
        )
        return

    expected_queue_id = request.get("queue_id")
    expected_work_item_id = request.get("work_item_id")
    expected_step_id = request.get("step_id")
    try:
        validate_pqx_execution_authority_record(
            proof,
            expected_queue_id=str(expected_queue_id) if _is_present(expected_queue_id) else None,
            expected_work_item_id=str(expected_work_item_id) if _is_present(expected_work_item_id) else None,
            expected_step_id=str(expected_step_id) if _is_present(expected_step_id) else None,
        )
    except (PqxExecutionAuthorityError, Exception) as exc:
        _add_violation(
            violations,
            code="pqx_entry_violation",
            boundary="PQX",
            field="artifact_references.pqx_execution_authority_record",
            message=f"PQX authority proof invalid: {exc}",
        )


def _check_artifact_boundary(normalized: dict[str, Any], violations: list[dict[str, Any]]) -> bool:
    refs = normalized["artifact_references"]
    missing: list[str] = []
    for key in _REQUIRED_CORE_ARTIFACT_KEYS:
        value = refs.get(key, normalized.get(key))
        if not _is_present(value):
            missing.append(key)

    if missing:
        _add_violation(
            violations,
            code="missing_artifact_violation",
            boundary="ARTIFACT",
            field="artifact_references",
            message=f"required artifacts missing or malformed: {', '.join(sorted(missing))}",
        )
        return False
    return True


def _check_tpa_boundary(normalized: dict[str, Any], violations: list[dict[str, Any]]) -> None:
    request = normalized["execution_request"]
    if not bool(request.get("tpa_required")):
        return
    refs = normalized["artifact_references"]
    missing = [
        key
        for key in ("tpa_lineage_artifact", "tpa_artifact")
        if not _is_present(refs.get(key))
    ]
    if missing:
        _add_violation(
            violations,
            code="tpa_boundary_violation",
            boundary="TPA",
            field="artifact_references",
            message=f"missing required TPA evidence: {', '.join(sorted(missing))}",
        )


def _check_fre_boundary(normalized: dict[str, Any], violations: list[dict[str, Any]]) -> None:
    request = normalized["execution_request"]
    if not bool(request.get("recovery_involved")):
        return
    refs = normalized["artifact_references"]
    required = (
        "failure_diagnosis_artifact",
        "repair_prompt_artifact",
        "recovery_result_artifact",
    )
    missing = [key for key in required if not _is_present(refs.get(key))]
    if missing:
        _add_violation(
            violations,
            code="fre_boundary_violation",
            boundary="FRE",
            field="artifact_references",
            message=f"partial recovery flow detected; missing: {', '.join(sorted(missing))}",
        )


def _check_ril_intake_boundary(normalized: dict[str, Any], violations: list[dict[str, Any]]) -> None:
    downstream = normalized["downstream_consumption"]
    consumed = downstream.get("consumed_artifact_types", [])
    if not isinstance(consumed, list):
        consumed = []
    normalized_types = [str(item).strip() for item in consumed if str(item).strip()]

    prohibited = sorted(set(item for item in normalized_types if item in _REJECTED_RIL_INTAKE_TYPES))
    non_projection = sorted(set(item for item in normalized_types if item not in _ALLOWED_RIL_INTAKE_TYPES))

    if prohibited or non_projection:
        details = []
        if prohibited:
            details.append(f"prohibited types: {', '.join(prohibited)}")
        if non_projection:
            details.append(f"non-projection types: {', '.join(non_projection)}")
        _add_violation(
            violations,
            code="ril_boundary_violation",
            boundary="RIL",
            field="downstream_consumption.consumed_artifact_types",
            message="downstream consumers must only use projection artifacts; " + "; ".join(details),
        )


def _check_governance_evidence(normalized: dict[str, Any], violations: list[dict[str, Any]]) -> None:
    governance = normalized["governance_evidence"]
    request = normalized["execution_request"]

    required = ["preflight_evidence", "control_evidence"]
    if bool(request.get("certification_required")):
        required.append("certification_evidence")

    missing = [key for key in required if not _is_present(governance.get(key))]
    if missing:
        _add_violation(
            violations,
            code="governance_evidence_violation",
            boundary="GOVERNANCE_EVIDENCE",
            field="governance_evidence",
            message=f"missing required governance evidence: {', '.join(sorted(missing))}",
        )


def _check_lineage(normalized: dict[str, Any], violations: list[dict[str, Any]]) -> None:
    lineage = normalized["lineage"]
    trace_refs = normalized["trace_refs"]

    lineage_id = lineage.get("lineage_id")
    parent_refs = lineage.get("parent_refs")

    parent_refs_valid = isinstance(parent_refs, list) and all(_is_present(item) for item in parent_refs)
    trace_refs_valid = isinstance(trace_refs, list) and len(trace_refs) > 0 and all(_is_present(item) for item in trace_refs)

    if not _is_present(lineage_id) or not parent_refs_valid or not trace_refs_valid:
        _add_violation(
            violations,
            code="lineage_violation",
            boundary="LINEAGE",
            field="lineage/trace_refs",
            message="lineage must include lineage_id, parent_refs, and trace_refs for traceable artifact lineage",
        )


def _check_repair_boundaries(normalized: dict[str, Any], violations: list[dict[str, Any]]) -> None:
    request = normalized["execution_request"]
    refs = normalized["artifact_references"]
    if not bool(request.get("repair_attempt", False)):
        return

    required = "failure_repair_candidate_artifact"
    if not _is_present(refs.get(required)):
        _add_violation(
            violations,
            code="missing_artifact_violation",
            boundary="REPAIR",
            field=f"artifact_references.{required}",
            message=f"repair attempt missing required governed artifact: {required}",
        )

    decision_state = str(request.get("repair_decision_state") or "").strip()
    if decision_state != "continue_repair_bounded":
        _add_violation(
            violations,
            code="repair_decision_violation",
            boundary="REPAIR",
            field="execution_request.repair_decision_state",
            message="repair execution requires continue_repair_bounded decision state",
        )

    budget_remaining = request.get("repair_budget_remaining")
    if not isinstance(budget_remaining, int) or budget_remaining < 0:
        _add_violation(
            violations,
            code="repair_budget_violation",
            boundary="REPAIR",
            field="execution_request.repair_budget_remaining",
            message="repair budget must be present and non-negative",
        )
    elif budget_remaining == 0:
        _add_violation(
            violations,
            code="repair_budget_violation",
            boundary="REPAIR",
            field="execution_request.repair_budget_remaining",
            message="repair budget exhausted; no further repair attempts allowed",
        )

    approved_scope = request.get("approved_repair_scope")
    touched_files = request.get("repair_files_touched")
    if not isinstance(approved_scope, list) or not approved_scope:
        _add_violation(
            violations,
            code="repair_scope_violation",
            boundary="REPAIR",
            field="execution_request.approved_repair_scope",
            message="repair attempts require non-empty approved scope",
        )
        return
    if not isinstance(touched_files, list) or not touched_files:
        _add_violation(
            violations,
            code="repair_scope_violation",
            boundary="REPAIR",
            field="execution_request.repair_files_touched",
            message="repair attempts must declare touched files",
        )
        return

    approved = {str(item).strip() for item in approved_scope if isinstance(item, str) and item.strip()}
    touched = {str(item).strip() for item in touched_files if isinstance(item, str) and item.strip()}
    outside = sorted(path for path in touched if path not in approved)
    if outside:
        _add_violation(
            violations,
            code="repair_scope_violation",
            boundary="REPAIR",
            field="execution_request.repair_files_touched",
            message=f"repair touched files outside approved scope: {', '.join(outside)}",
        )


def _check_failure_learning_governance(normalized: dict[str, Any], violations: list[dict[str, Any]]) -> None:
    request = normalized["execution_request"]
    refs = normalized["artifact_references"]
    if not bool(request.get("failure_learning_required", False)):
        return

    if not _is_present(refs.get("failure_class_registry")):
        _add_violation(
            violations,
            code="failure_class_registry_violation",
            boundary="FRE",
            field="artifact_references.failure_class_registry",
            message="failure class must exist in canonical registry",
        )
    if _is_present(refs.get("eval_candidate_artifact")) and not _is_present(refs.get("eval_adoption_decision_artifact")):
        _add_violation(
            violations,
            code="eval_adoption_violation",
            boundary="CDE",
            field="artifact_references.eval_adoption_decision_artifact",
            message="eval adoption decision must exist before eval is used",
        )
    if _is_present(refs.get("roadmap_signal_artifact")) and not _is_present(refs.get("failure_learning_record_artifact")):
        _add_violation(
            violations,
            code="roadmap_signal_linkage_violation",
            boundary="PRG",
            field="artifact_references.failure_learning_record_artifact",
            message="roadmap signal must reference failure learning artifacts",
        )


def _check_closure_authority_boundaries(normalized: dict[str, Any], violations: list[dict[str, Any]]) -> None:
    request = normalized["execution_request"]
    refs = normalized["artifact_references"]

    closure_source = request.get("closure_decision_source")
    readiness_source = request.get("promotion_readiness_decisioning")
    if _is_present(closure_source):
        _add_violation(
            violations,
            code="repair_decision_violation",
            boundary="CDE",
            field="execution_request.closure_decision_source",
            message="raw closure source flags are non-authoritative; provide a real closure_decision_artifact",
        )
    if _is_present(readiness_source):
        _add_violation(
            violations,
            code="repair_decision_violation",
            boundary="CDE",
            field="execution_request.promotion_readiness_decisioning",
            message="raw readiness source flags are non-authoritative; provide a real closure_decision_artifact",
        )

    closure_artifact = refs.get("closure_decision_artifact")
    closure_ref = refs.get("closure_decision_artifact_ref")
    closure_state = str(request.get("closure_state") or "OPEN").strip().upper()

    if (
        closure_state == "OPEN"
        and not _is_present(closure_artifact)
        and not _is_present(closure_ref)
        and not _is_present(closure_source)
        and not _is_present(readiness_source)
    ):
        return

    if not isinstance(closure_artifact, dict):
        _add_violation(
            violations,
            code="missing_artifact_violation",
            boundary="CDE",
            field="artifact_references.closure_decision_artifact",
            message="SEL enforcement requires a real closure_decision_artifact from CDE",
        )
        return
    try:
        validate_artifact(closure_artifact, "closure_decision_artifact")
    except Exception as exc:
        _add_violation(
            violations,
            code="missing_artifact_violation",
            boundary="CDE",
            field="artifact_references.closure_decision_artifact",
            message=f"closure_decision_artifact is invalid: {exc}",
        )
        return

    if not _is_present(closure_ref):
        _add_violation(
            violations,
            code="lineage_violation",
            boundary="CDE",
            field="artifact_references.closure_decision_artifact_ref",
            message="closure decision artifact must include deterministic CDE reference",
        )

    if closure_state not in {"OPEN", "LOCKED", "CLOSED"}:
        _add_violation(
            violations,
            code="repair_budget_violation",
            boundary="SEL",
            field="execution_request.closure_state",
            message="closure_state must be one of OPEN, LOCKED, CLOSED",
        )
    elif closure_state != "OPEN":
        _add_violation(
            violations,
            code="repair_budget_violation",
            boundary="SEL",
            field="execution_request.closure_state",
            message="execution is blocked when closure_state is not OPEN",
        )


def _parse_dt(value: Any, *, field: str, violations: list[dict[str, Any]]) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        _add_violation(
            violations,
            code="governance_evidence_violation",
            boundary="SEL",
            field=field,
            message=f"{field} must be a non-empty RFC3339 timestamp",
        )
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _add_violation(
            violations,
            code="governance_evidence_violation",
            boundary="SEL",
            field=field,
            message=f"{field} must be a valid RFC3339 timestamp",
        )
        return None


def enforce_preflight_remediation_boundaries(*, remediation_context: dict[str, Any]) -> dict[str, Any]:
    """Enforce SEL fail-closed preflight remediation constraints."""
    if not isinstance(remediation_context, dict):
        raise SystemEnforcementLayerError("remediation_context must be an object")

    violations: list[dict[str, Any]] = []
    lineage = remediation_context.get("lineage")
    if not isinstance(lineage, dict):
        _add_violation(
            violations,
            code="lineage_violation",
            boundary="AEX",
            field="lineage",
            message="repair attempt requires AEX/TLC lineage continuity",
        )
    else:
        required_lineage = ("request_ref", "admission_ref", "tlc_handoff_ref", "trace_id")
        missing_lineage = [key for key in required_lineage if not _is_present(lineage.get(key))]
        if missing_lineage:
            _add_violation(
                violations,
                code="lineage_violation",
                boundary="AEX",
                field="lineage",
                message=f"lineage missing required refs: {', '.join(sorted(missing_lineage))}",
            )

    packet = remediation_context.get("failure_packet")
    candidate = remediation_context.get("repair_candidate")
    continuation_decision = remediation_context.get("continuation_decision")
    continuation_input = remediation_context.get("continuation_input")
    gating_input = remediation_context.get("gating_input")
    if not isinstance(packet, dict) or not isinstance(candidate, dict):
        _add_violation(
            violations,
            code="missing_artifact_violation",
            boundary="ARTIFACT",
            field="failure_packet/repair_candidate",
            message="canonical failure packet and bounded repair candidate are required",
        )
    if not isinstance(continuation_decision, dict) or str(continuation_decision.get("owner")) != "CDE":
        _add_violation(
            violations,
            code="repair_decision_violation",
            boundary="CDE",
            field="continuation_decision",
            message="bounded repair continuation requires authoritative CDE decision",
        )
    if not isinstance(continuation_input, dict):
        _add_violation(
            violations,
            code="repair_decision_violation",
            boundary="CDE",
            field="continuation_input",
            message="CDE continuation input artifact is required",
        )
    if not isinstance(gating_input, dict):
        _add_violation(
            violations,
            code="tpa_boundary_violation",
            boundary="TPA",
            field="gating_input",
            message="TPA gating input is required for bounded repair execution",
        )
    if isinstance(continuation_input, dict) and isinstance(packet, dict) and isinstance(candidate, dict):
        expected_failure_digest = _hash16(packet)
        expected_candidate_digest = _hash16(candidate)
        if not str(continuation_input.get("failure_packet_digest", "")).startswith(expected_failure_digest):
            _add_violation(
                violations,
                code="governance_evidence_violation",
                boundary="CDE",
                field="continuation_input.failure_packet_digest",
                message="continuation input failure digest does not bind to failure packet",
            )
        if not str(continuation_input.get("repair_candidate_digest", "")).startswith(expected_candidate_digest):
            _add_violation(
                violations,
                code="governance_evidence_violation",
                boundary="CDE",
                field="continuation_input.repair_candidate_digest",
                message="continuation input candidate digest does not bind to repair candidate",
            )
        issued_at = _parse_dt(continuation_input.get("issued_at"), field="continuation_input.issued_at", violations=violations)
        freshness = continuation_input.get("freshness_window_seconds")
        if not isinstance(freshness, int) or freshness < 1:
            _add_violation(
                violations,
                code="repair_budget_violation",
                boundary="CDE",
                field="continuation_input.freshness_window_seconds",
                message="continuation input freshness_window_seconds must be >= 1",
            )
        elif issued_at is not None:
            elapsed = (datetime.now(tz=timezone.utc) - issued_at.astimezone(timezone.utc)).total_seconds()
            if elapsed > freshness:
                _add_violation(
                    violations,
                    code="governance_evidence_violation",
                    boundary="CDE",
                    field="continuation_input",
                    message="continuation authority evidence is stale",
                )

    retry_budget_remaining = remediation_context.get("retry_budget_remaining")
    if not isinstance(retry_budget_remaining, int) or retry_budget_remaining < 0:
        _add_violation(
            violations,
            code="repair_budget_violation",
            boundary="SEL",
            field="retry_budget_remaining",
            message="retry budget must be a non-negative integer",
        )
    elif retry_budget_remaining <= 0:
        _add_violation(
            violations,
            code="repair_budget_violation",
            boundary="SEL",
            field="retry_budget_remaining",
            message="retry budget exhausted",
        )

    approved_scope_refs = remediation_context.get("approved_scope_refs")
    execution_scope_refs = remediation_context.get("execution_scope_refs")
    approved = set(str(item).strip() for item in (approved_scope_refs or []) if isinstance(item, str) and item.strip())
    executed = set(str(item).strip() for item in (execution_scope_refs or []) if isinstance(item, str) and item.strip())
    if not approved:
        _add_violation(
            violations,
            code="repair_scope_violation",
            boundary="TPA",
            field="approved_scope_refs",
            message="TPA-approved bounded scope is required",
        )
    if executed - approved:
        _add_violation(
            violations,
            code="repair_scope_violation",
            boundary="PQX",
            field="execution_scope_refs",
            message="execution attempted beyond TPA-approved bounded scope",
        )
    if isinstance(gating_input, dict):
        scope_digest = gating_input.get("approved_scope_digest")
        expected_scope_digest = hashlib.sha256(
            json.dumps(sorted(approved), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        if not isinstance(scope_digest, str) or scope_digest != expected_scope_digest:
            _add_violation(
                violations,
                code="repair_scope_violation",
                boundary="TPA",
                field="gating_input.approved_scope_digest",
                message="approved scope digest mismatch; overscope or path drift detected",
            )
        issued_at = _parse_dt(gating_input.get("issued_at"), field="gating_input.issued_at", violations=violations)
        freshness = gating_input.get("freshness_window_seconds")
        if not isinstance(freshness, int) or freshness < 1:
            _add_violation(
                violations,
                code="repair_budget_violation",
                boundary="TPA",
                field="gating_input.freshness_window_seconds",
                message="TPA gating freshness_window_seconds must be >= 1",
            )
        elif issued_at is not None:
            elapsed = (datetime.now(tz=timezone.utc) - issued_at.astimezone(timezone.utc)).total_seconds()
            if elapsed > freshness:
                _add_violation(
                    violations,
                    code="governance_evidence_violation",
                    boundary="TPA",
                    field="gating_input",
                    message="TPA gating evidence is stale",
                )

    rerun_preflight = remediation_context.get("rerun_preflight_result")
    if rerun_preflight is not None:
        if not isinstance(rerun_preflight, dict):
            _add_violation(
                violations,
                code="governance_evidence_violation",
                boundary="RIL",
                field="rerun_preflight_result",
                message="rerun preflight evidence must be a structured artifact",
            )
        elif not _is_present(rerun_preflight.get("control_signal")):
            _add_violation(
                violations,
                code="governance_evidence_violation",
                boundary="RIL",
                field="rerun_preflight_result.control_signal",
                message="rerun preflight evidence missing control_signal",
            )
        rerun_execution_record = remediation_context.get("rerun_execution_record")
        if not isinstance(rerun_execution_record, dict):
            _add_violation(
                violations,
                code="governance_evidence_violation",
                boundary="PQX",
                field="rerun_execution_record",
                message="rerun requires PQX preflight execution record",
            )
        elif not _is_present(rerun_execution_record.get("evidence_digest")):
            _add_violation(
                violations,
                code="governance_evidence_violation",
                boundary="PQX",
                field="rerun_execution_record.evidence_digest",
                message="rerun execution record missing evidence digest",
            )
        diagnosis_artifact = remediation_context.get("diagnosis_artifact")
        terminal = remediation_context.get("terminal_classification")
        if not isinstance(diagnosis_artifact, dict) or diagnosis_artifact.get("artifact_type") != "failure_diagnosis_artifact":
            _add_violation(
                violations,
                code="fre_boundary_violation",
                boundary="FRE",
                field="diagnosis_artifact",
                message="promotion/continuation requires FRE diagnosis artifact",
            )
        if not isinstance(terminal, dict) or str(terminal.get("owner")) != "CDE":
            _add_violation(
                violations,
                code="repair_decision_violation",
                boundary="CDE",
                field="terminal_classification",
                message="promotion/continuation requires CDE terminal classification",
            )
        if isinstance(terminal, dict) and terminal.get("terminal_classification") in {"ambiguous_block", "block"}:
            _add_violation(
                violations,
                code="repair_decision_violation",
                boundary="CDE",
                field="terminal_classification",
                message="ambiguous terminal classification blocks by default",
            )
    elif remediation_context.get("missing_evidence_branch") or remediation_context.get("ambiguous_state_branch"):
        _add_violation(
            violations,
            code="governance_evidence_violation",
            boundary="SEL",
            field="rerun_preflight_result",
            message="retry branch without rerun evidence is blocked",
        )

    if remediation_context.get("repeated_retry_branch"):
        _add_violation(
            violations,
            code="repair_budget_violation",
            boundary="SEL",
            field="repeated_retry_branch",
            message="repeated bounded retry branch exhausted deterministic retry stop",
        )

    return {
        "artifact_type": "system_enforcement_result_artifact",
        "schema_version": "1.0.0",
        "enforcement_result_id": f"sel-rem-{_hash16({'violations': violations, 'lineage': lineage, 'scope': sorted(approved)})}",
        "enforcement_status": "block" if violations else "allow",
        "violations": violations,
        "violated_boundaries": sorted({str(item['boundary']) for item in violations}),
        "source_context": {"source_module": "preflight_remediation_loop", "caller_identity": "TLC"},
        "required_artifacts_present": not violations,
        "trace_refs": [str(lineage.get("trace_id"))] if isinstance(lineage, dict) and _is_present(lineage.get("trace_id")) else [],
        "emitted_at": "1970-01-01T00:00:00Z",
    }


def enforce_system_boundaries(context: dict[str, Any]) -> dict[str, Any]:
    """Enforce SEL governed boundaries; fail closed when any boundary violation exists."""

    if not isinstance(context, dict):
        raise SystemEnforcementLayerError("context must be a JSON-object-compatible mapping")

    normalized = _normalize_context(context)
    violations: list[dict[str, Any]] = []

    _check_pqx_entry(normalized, violations)
    required_artifacts_present = _check_artifact_boundary(normalized, violations)
    _check_tpa_boundary(normalized, violations)
    _check_fre_boundary(normalized, violations)
    _check_ril_intake_boundary(normalized, violations)
    _check_governance_evidence(normalized, violations)
    _check_lineage(normalized, violations)
    _check_repair_boundaries(normalized, violations)
    _check_failure_learning_governance(normalized, violations)
    _check_closure_authority_boundaries(normalized, violations)

    violated_boundaries = sorted({str(item["boundary"]) for item in violations})
    payload_for_id = {
        "source_context": {
            "source_module": normalized["source_module"],
            "caller_identity": normalized["caller_identity"],
            "execution_request": normalized["execution_request"],
        },
        "violations": violations,
        "required_artifacts_present": required_artifacts_present,
        "trace_refs": normalized["trace_refs"],
        "violated_boundaries": violated_boundaries,
        "emitted_at": normalized["emitted_at"],
    }

    result = {
        "artifact_type": "system_enforcement_result_artifact",
        "schema_version": "1.0.0",
        "enforcement_result_id": f"sel-{_hash16(payload_for_id)}",
        "enforcement_status": "block" if violations else "allow",
        "violations": violations,
        "violated_boundaries": violated_boundaries,
        "source_context": payload_for_id["source_context"],
        "required_artifacts_present": required_artifacts_present,
        "trace_refs": normalized["trace_refs"],
        "emitted_at": normalized["emitted_at"],
    }

    validator = Draft202012Validator(load_schema("system_enforcement_result_artifact"))
    errors = sorted(validator.iter_errors(result), key=lambda err: str(list(err.absolute_path)))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise SystemEnforcementLayerError(f"system enforcement result failed schema validation: {details}")

    return result
