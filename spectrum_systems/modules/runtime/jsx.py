"""JSX — Judgment State eXchange."""

from __future__ import annotations

from typing import Any

_VALID_STATUSES = {"active", "deprecated", "revoked"}


def set_judgment_status(*, judgment_record: dict[str, Any], status: str, reason: str) -> dict[str, Any]:
    normalized = status.strip().lower()
    if normalized not in _VALID_STATUSES:
        raise ValueError(f"invalid judgment status: {status}")
    updated = dict(judgment_record)
    updated["status"] = normalized
    updated["status_reason"] = reason
    return updated


def supersede_judgment(*, old_judgment_id: str, new_judgment_id: str, reason: str) -> dict[str, Any]:
    return {
        "artifact_type": "judgment_supersession_record",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "supersession_id": f"JSP-{old_judgment_id}-{new_judgment_id}",
        "old_judgment_id": old_judgment_id,
        "new_judgment_id": new_judgment_id,
        "reason": reason,
    }


def build_active_judgment_set(*, judgments: list[dict[str, Any]]) -> dict[str, Any]:
    active = [j for j in judgments if str(j.get("status")) == "active"]
    return {
        "artifact_type": "judgment_active_set_record",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "active_judgment_ids": sorted(str(item["judgment_id"]) for item in active),
        "active_count": len(active),
    }


def detect_judgment_conflicts(*, judgments: list[dict[str, Any]]) -> dict[str, Any]:
    seen: dict[str, str] = {}
    conflicts: list[dict[str, str]] = []
    for judgment in judgments:
        key = str(judgment.get("policy_key") or "")
        value = str(judgment.get("policy_value") or "")
        if not key:
            continue
        previous = seen.get(key)
        if previous is not None and previous != value:
            conflicts.append({"policy_key": key, "existing_value": previous, "new_value": value})
        seen[key] = value
    return {
        "artifact_type": "judgment_conflict_record",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "has_conflicts": len(conflicts) > 0,
        "conflicts": conflicts,
    }


def emit_judgment_policy_extraction_record(*, active_set: dict[str, Any], conflict_record: dict[str, Any], extraction_target: str) -> dict[str, Any]:
    return {
        "artifact_type": "judgment_policy_extraction_record",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "extraction_id": f"JPE-{extraction_target}-{active_set.get('active_count', 0)}",
        "active_set_ref": active_set,
        "conflict_ref": conflict_record,
        "target": extraction_target,
        "ready": bool(active_set.get("active_count", 0) >= 1) and not bool(conflict_record.get("has_conflicts", False)),
    }
