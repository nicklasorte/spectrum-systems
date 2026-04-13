"""REL release engineering governance runtime."""
from __future__ import annotations

from typing import Any, Mapping

from spectrum_systems.contracts import validate_artifact


def build_canary_metrics(*, sli_name: str, control_value: float, canary_value: float, error_budget_remaining: float, created_at: str, artifact_id: str = "rel-canary-001") -> dict[str, Any]:
    status = "pass" if canary_value <= control_value * 1.25 else "fail"
    rec = {
        "artifact_type": "rel_canary_metrics_breakdown",
        "artifact_id": artifact_id,
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.3.130",
        "created_at": created_at,
        "sli_name": sli_name,
        "control_value": control_value,
        "canary_value": canary_value,
        "error_budget_remaining": error_budget_remaining,
        "status": status,
    }
    validate_artifact(rec, "rel_canary_metrics_breakdown")
    return rec


def freeze_on_budget(*, error_budget_remaining: float, created_at: str, artifact_id: str = "rel-freeze-001") -> dict[str, Any]:
    freeze = error_budget_remaining <= 0
    rec = {
        "artifact_type": "rel_change_freeze_record",
        "artifact_id": artifact_id,
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.3.130",
        "created_at": created_at,
        "freeze": freeze,
        "reason_codes": ["budget_exhausted"] if freeze else ["budget_available"],
        "error_budget_remaining": error_budget_remaining,
    }
    validate_artifact(rec, "rel_change_freeze_record")
    return rec


def build_release_record(*, change_type: str, canary_metrics: Mapping[str, Any], freeze_record: Mapping[str, Any], evidence_refs: list[str], certification_ref: str, created_at: str, artifact_id: str = "rel-release-001") -> dict[str, Any]:
    blocked = freeze_record["freeze"] or canary_metrics["status"] == "fail" or not evidence_refs
    status = "block" if blocked else "pass"
    rec = {
        "artifact_type": "rel_release_record",
        "artifact_id": artifact_id,
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.3.130",
        "created_at": created_at,
        "change_type": change_type,
        "status": status,
        "evidence_refs": evidence_refs,
        "canary_ref": f"rel_canary_metrics_breakdown:{canary_metrics.get('artifact_id')}",
        "certification_ref": certification_ref,
    }
    validate_artifact(rec, "rel_release_record")
    return rec
