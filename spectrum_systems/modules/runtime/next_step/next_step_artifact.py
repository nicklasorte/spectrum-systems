from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


REQUIRED_TOP_LEVEL_KEYS = {
    "artifact_type",
    "schema_version",
    "generated_at",
    "status",
    "readiness_state",
    "source_refs",
    "completed_work",
    "partial_work",
    "remaining_work_table",
    "ranked_priorities",
    "selected_next_step",
    "rejected_next_steps",
    "dependency_reasoning",
    "red_team_findings",
    "warnings",
    "reason_codes",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def validate_artifact_shape(payload: dict[str, Any]) -> None:
    missing = REQUIRED_TOP_LEVEL_KEYS - set(payload.keys())
    if missing:
        raise ValueError(f"artifact missing required keys: {sorted(missing)}")
    if payload["artifact_type"] != "next_step_decision_report":
        raise ValueError("artifact_type must be next_step_decision_report")
    if payload["schema_version"] != "1.0.0":
        raise ValueError("schema_version must be 1.0.0")
    if payload["status"] not in {"pass", "blocked"}:
        raise ValueError("status must be pass|blocked")
    if payload["readiness_state"] not in {"ready", "blocked"}:
        raise ValueError("readiness_state must be ready|blocked")



def blocked_payload(reason_codes: list[str], source_refs: list[dict[str, Any]], warnings: list[str]) -> dict[str, Any]:
    payload = {
        "artifact_type": "next_step_decision_report",
        "schema_version": "1.0.0",
        "generated_at": utc_now_iso(),
        "status": "blocked",
        "readiness_state": "blocked",
        "source_refs": source_refs,
        "completed_work": [],
        "partial_work": [],
        "remaining_work_table": [],
        "ranked_priorities": [],
        "selected_next_step": None,
        "rejected_next_steps": [],
        "dependency_reasoning": [],
        "red_team_findings": [],
        "warnings": warnings,
        "reason_codes": sorted(set(reason_codes)),
    }
    validate_artifact_shape(payload)
    return payload
