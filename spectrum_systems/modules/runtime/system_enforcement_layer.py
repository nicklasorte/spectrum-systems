"""System Enforcement Layer (SEL-001): explicit fail-closed governed boundary enforcement."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from jsonschema import Draft202012Validator

from spectrum_systems.contracts import load_schema

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
