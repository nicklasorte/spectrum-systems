"""RUX reuse governance runtime."""
from __future__ import annotations

from typing import Any, Mapping

from spectrum_systems.contracts import validate_artifact


class RUXRuntimeError(ValueError):
    pass


def create_reuse_record(*, asset_ref: str, asset_type: str, justification: str, scope: str, freshness_hours: float, lineage_ref: str, active_set_valid: bool, created_at: str, artifact_id: str = "rux-reuse-001") -> dict[str, Any]:
    if not justification:
        raise RUXRuntimeError("missing_justification")
    if not lineage_ref:
        raise RUXRuntimeError("missing_lineage_ref")
    rec = {
        "artifact_type": "rux_reuse_record",
        "artifact_id": artifact_id,
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.3.130",
        "created_at": created_at,
        "asset_ref": asset_ref,
        "asset_type": asset_type,
        "justification": justification,
        "scope": scope,
        "freshness_hours": freshness_hours,
        "lineage_ref": lineage_ref,
        "active_set_valid": active_set_valid,
    }
    validate_artifact(rec, "rux_reuse_record")
    return rec


def enforce_reuse_boundary(*, reuse_record: Mapping[str, Any], allowed_scopes: set[str], freshness_limit_hours: float) -> tuple[dict[str, Any], dict[str, Any]]:
    violations = []
    freshness_ok = reuse_record.get("freshness_hours", 10**9) <= freshness_limit_hours
    scope_ok = reuse_record.get("scope") in allowed_scopes
    active_set_ok = bool(reuse_record.get("active_set_valid"))
    if not freshness_ok:
        violations.append("stale_reuse")
    if not scope_ok:
        violations.append("out_of_scope_reuse")
    if not active_set_ok:
        violations.append("inactive_or_superseded_asset")
    status = "pass" if not violations else "fail"
    boundary = {
        "artifact_type": "rux_boundary_validation_result",
        "artifact_id": f"rux-boundary-{reuse_record.get('artifact_id', 'unknown')}",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.3.130",
        "created_at": reuse_record["created_at"],
        "reuse_ref": f"rux_reuse_record:{reuse_record.get('artifact_id')}",
        "status": status,
        "violations": violations,
    }
    report = {
        "artifact_type": "rux_freshness_scope_report",
        "artifact_id": f"rux-freshness-{reuse_record.get('artifact_id', 'unknown')}",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.3.130",
        "created_at": reuse_record["created_at"],
        "reuse_ref": f"rux_reuse_record:{reuse_record.get('artifact_id')}",
        "freshness_ok": freshness_ok,
        "scope_ok": scope_ok,
        "active_set_ok": active_set_ok,
        "reason_codes": violations or ["fresh"],
    }
    validate_artifact(boundary, "rux_boundary_validation_result")
    validate_artifact(report, "rux_freshness_scope_report")
    return boundary, report
