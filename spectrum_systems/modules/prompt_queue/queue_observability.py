"""Read-only deterministic queue observability snapshot generation."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from spectrum_systems.modules.prompt_queue.queue_state_machine import _ALLOWED_TRANSITIONS

_REQUIRED_WORK_ITEM_FIELDS = (
    "work_item_id",
    "status",
    "retry_count",
    "retry_budget",
)

_RUNNING_STATUSES = {
    "review_running",
    "review_fallback_running",
    "executing",
    "review_invoking",
}

_COMPLETED_STATUSES = {
    "review_complete",
    "complete",
    "executed_success",
    "review_invocation_succeeded",
}

_FAILED_STATUSES = {
    "review_provider_failed",
    "executed_failure",
    "review_invocation_failed",
    "reentry_blocked",
}

_QUEUED_STATUSES = {
    "queued",
    "review_queued",
    "review_triggered",
    "runnable",
    "execution_gated",
    "repair_child_created",
    "repair_prompt_generated",
    "findings_parsed",
    "review_required",
    "reentry_eligible",
    "approval_required",
}


def _status_bucket(status: str) -> str | None:
    if status == "blocked":
        return "blocked"
    if status in _RUNNING_STATUSES:
        return "running"
    if status in _COMPLETED_STATUSES:
        return "completed"
    if status in _FAILED_STATUSES:
        return "failed"
    if status in _QUEUED_STATUSES:
        return "queued"
    return None


def validate_queue_invariants(queue_state: dict[str, Any]) -> list[str]:
    """Return deterministic invariant violations without mutating input state."""
    violations: list[str] = []
    work_items = sorted(queue_state.get("work_items", []), key=lambda item: str(item.get("work_item_id", "")))

    run_id_to_items: dict[str, list[str]] = {}
    for item in work_items:
        work_item_id = str(item.get("work_item_id", "<missing_work_item_id>"))
        missing_fields = [field for field in _REQUIRED_WORK_ITEM_FIELDS if field not in item]
        if missing_fields:
            violations.append(f"missing_required_fields:{work_item_id}:{','.join(missing_fields)}")
            continue

        status = item["status"]
        retry_count = item["retry_count"]
        retry_budget = item["retry_budget"]

        if not isinstance(retry_count, int) or not isinstance(retry_budget, int):
            violations.append(f"invalid_retry_types:{work_item_id}")
        elif retry_count > retry_budget:
            violations.append(
                f"retry_count_exceeds_budget:{work_item_id}:retry_count={retry_count}:retry_budget={retry_budget}"
            )

        if item.get("is_blocked") is True and item.get("is_running") is True:
            violations.append(f"blocked_and_running_flags:{work_item_id}")
        if status == "blocked" and item.get("is_running") is True:
            violations.append(f"blocked_status_with_running_flag:{work_item_id}")
        if status in _RUNNING_STATUSES and item.get("is_blocked") is True:
            violations.append(f"running_status_with_blocked_flag:{work_item_id}")

        previous_status = item.get("previous_status")
        if previous_status is not None:
            allowed = _ALLOWED_TRANSITIONS.get(previous_status, set())
            if status not in allowed:
                violations.append(
                    f"invalid_state_transition:{work_item_id}:{previous_status}->{status}"
                )

        if status not in _ALLOWED_TRANSITIONS:
            violations.append(f"unknown_status:{work_item_id}:{status}")

        run_id = item.get("run_id")
        if isinstance(run_id, str) and run_id:
            run_id_to_items.setdefault(run_id, []).append(work_item_id)

    for run_id in sorted(run_id_to_items):
        work_item_ids = sorted(run_id_to_items[run_id])
        if len(work_item_ids) > 1:
            violations.append(f"duplicate_run_id:{run_id}:{','.join(work_item_ids)}")

    return sorted(violations)


def generate_queue_snapshot(queue_state: dict[str, Any]) -> dict[str, Any]:
    """Generate a deterministic, schema-backed observability snapshot from queue state."""
    work_items = sorted(queue_state.get("work_items", []), key=lambda item: str(item.get("work_item_id", "")))

    items_by_status = {
        "queued": 0,
        "running": 0,
        "completed": 0,
        "failed": 0,
        "blocked": 0,
    }
    retry_counts: list[int] = []
    active_run_ids: list[str] = []

    for item in work_items:
        status = str(item.get("status", ""))
        bucket = _status_bucket(status)
        if bucket is not None:
            items_by_status[bucket] += 1

        retry_count = item.get("retry_count", 0)
        retry_counts.append(retry_count if isinstance(retry_count, int) else 0)

        run_id = item.get("run_id")
        if isinstance(run_id, str) and run_id and status in _RUNNING_STATUSES:
            active_run_ids.append(run_id)

    exhausted_retry_count = 0
    for item in work_items:
        retry_count = item.get("retry_count")
        retry_budget = item.get("retry_budget")
        if isinstance(retry_count, int) and isinstance(retry_budget, int) and retry_count >= retry_budget:
            exhausted_retry_count += 1

    invariants = validate_queue_invariants(queue_state)
    snapshot_timestamp = str(queue_state.get("updated_at") or queue_state.get("created_at") or "1970-01-01T00:00:00Z")

    snapshot_basis = {
        "queue_id": queue_state.get("queue_id"),
        "timestamp": snapshot_timestamp,
        "work_items": work_items,
        "invariants": invariants,
    }
    digest = hashlib.sha256(json.dumps(snapshot_basis, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    return {
        "snapshot_id": f"pqo-{digest[:16]}",
        "timestamp": snapshot_timestamp,
        "total_items": len(work_items),
        "items_by_status": items_by_status,
        "retry_counts_summary": {
            "total_retry_count": sum(retry_counts),
            "max_retry_count": max(retry_counts) if retry_counts else 0,
            "items_with_retries": sum(1 for count in retry_counts if count > 0),
        },
        "blocked_items_count": items_by_status["blocked"],
        "exhausted_retry_count": exhausted_retry_count,
        "active_run_ids": sorted(set(active_run_ids)),
        "invariant_violations": invariants,
    }
