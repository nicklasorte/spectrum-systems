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

_HEALTH_STATES = {"stable", "degraded", "unstable"}

_UNSTABLE_INVARIANT_PREFIXES = {
    "invalid_state_transition",
    "unknown_status",
    "duplicate_run_id",
    "retry_count_exceeds_budget",
    "blocked_and_running_flags",
    "blocked_status_with_running_flag",
    "running_status_with_blocked_flag",
}

_REMEDIATION_STATUSES = {
    "findings_parsed",
    "repair_prompt_generated",
    "repair_child_created",
    "review_required",
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


def _derive_trace_linkage(queue_state: dict[str, Any], work_items: list[dict[str, Any]]) -> dict[str, str]:
    run_ids = sorted(
        {
            str(item.get("run_id"))
            for item in work_items
            if isinstance(item.get("run_id"), str) and str(item.get("run_id"))
        }
    )
    if run_ids:
        return {"linkage_type": "run_id", "linkage_id": run_ids[0]}

    step_results = queue_state.get("step_results", [])
    if isinstance(step_results, list):
        refs = sorted(
            {
                str(result.get("result_ref"))
                for result in step_results
                if isinstance(result, dict) and isinstance(result.get("result_ref"), str) and result["result_ref"]
            }
        )
        if refs:
            return {"linkage_type": "result_ref", "linkage_id": refs[-1]}

    raise ValueError("missing queue state lineage: no run_id or trace result_ref available")


def _derive_last_transition_action(queue_state: dict[str, Any]) -> str:
    step_results = queue_state.get("step_results", [])
    if not isinstance(step_results, list) or not step_results:
        return "none"

    last_result = step_results[-1]
    if not isinstance(last_result, dict):
        return "unknown"
    status = str(last_result.get("status", ""))
    if status == "blocked":
        return "block"
    if status == "completed":
        return "continue"
    return "unknown"


def _classify_health(metrics: dict[str, Any], invariants: list[str]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    required_metrics = {
        "queue_id",
        "current_step_index",
        "total_steps",
        "queue_status",
        "last_transition_action",
        "blocked_count",
        "retry_count",
        "remediation_count",
        "ambiguous_signal_count",
        "recovery_count",
        "completion_progress",
    }
    missing = sorted(metric for metric in required_metrics if metric not in metrics)
    if missing:
        return "degraded", [f"missing_required_metric:{metric}" for metric in missing]

    blocked_count = int(metrics["blocked_count"])
    ambiguous_count = int(metrics["ambiguous_signal_count"])
    completion_progress = float(metrics["completion_progress"])
    queue_status = str(metrics["queue_status"])

    unstable_invariants = sorted(
        violation
        for violation in invariants
        if any(violation.startswith(prefix) for prefix in _UNSTABLE_INVARIANT_PREFIXES)
    )
    if unstable_invariants:
        reasons.extend(f"unstable_invariant:{violation}" for violation in unstable_invariants)

    if ambiguous_count > 0:
        reasons.append("ambiguous_signals_present")

    if blocked_count > 0:
        reasons.append("blocked_items_present")

    if queue_status == "completed" and completion_progress < 1.0:
        reasons.append("conflicting_completion_signal")

    if queue_status != "completed" and completion_progress == 1.0:
        reasons.append("conflicting_completion_signal")

    if unstable_invariants or ambiguous_count >= 2 or (blocked_count > 0 and queue_status == "running"):
        return "unstable", sorted(set(reasons or ["unstable_condition_detected"]))

    if ambiguous_count > 0 or blocked_count > 0 or missing:
        return "degraded", sorted(set(reasons or ["degraded_condition_detected"]))

    return "stable", []


def _validate_snapshot_inputs(queue_state: dict[str, Any]) -> None:
    if not isinstance(queue_state, dict):
        raise ValueError("malformed queue_state input: expected object")

    required_queue_fields = {
        "queue_id",
        "queue_status",
        "work_items",
        "current_step_index",
        "total_steps",
        "step_results",
    }
    missing_queue_fields = sorted(field for field in required_queue_fields if field not in queue_state)
    if missing_queue_fields:
        raise ValueError(f"malformed queue_state input: missing required fields {', '.join(missing_queue_fields)}")

    if not isinstance(queue_state.get("work_items"), list):
        raise ValueError("malformed queue_state input: work_items must be a list")
    if not isinstance(queue_state.get("step_results"), list):
        raise ValueError("malformed queue_state input: step_results must be a list")


def generate_queue_snapshot(queue_state: dict[str, Any]) -> dict[str, Any]:
    """Generate a deterministic, schema-backed observability snapshot from queue state."""
    _validate_snapshot_inputs(queue_state)

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
    remediation_count = 0
    recovery_count = 0

    for item in work_items:
        status = str(item.get("status", ""))
        bucket = _status_bucket(status)
        if bucket is not None:
            items_by_status[bucket] += 1

        retry_count = item.get("retry_count", 0)
        retry_counts.append(retry_count if isinstance(retry_count, int) else 0)

        if status in _REMEDIATION_STATUSES or item.get("repair_prompt_artifact_path"):
            remediation_count += 1
        if item.get("blocked_recovery_decision_artifact_path"):
            recovery_count += 1

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
    last_transition_action = _derive_last_transition_action(queue_state)
    ambiguous_signal_count = sum(1 for violation in invariants if "ambiguous" in violation)
    if last_transition_action == "unknown":
        ambiguous_signal_count += 1
    if queue_state.get("queue_status") == "running" and queue_state.get("active_work_item_id") in {None, ""}:
        ambiguous_signal_count += 1
    snapshot_timestamp = str(queue_state.get("updated_at") or queue_state.get("created_at") or "1970-01-01T00:00:00Z")
    trace_linkage = _derive_trace_linkage(queue_state, work_items)
    queue_id = str(queue_state.get("queue_id", ""))
    if not queue_id:
        raise ValueError("missing queue state lineage: queue_id is required")

    current_step_index = int(queue_state.get("current_step_index", 0))
    total_steps = int(queue_state.get("total_steps", 0))
    completion_progress = 0.0 if total_steps <= 0 else round(current_step_index / total_steps, 4)

    health_metrics = {
        "queue_id": queue_id,
        "current_step_index": current_step_index,
        "total_steps": total_steps,
        "queue_status": str(queue_state.get("queue_status", "")),
        "last_transition_action": last_transition_action,
        "blocked_count": items_by_status["blocked"],
        "retry_count": sum(retry_counts),
        "remediation_count": remediation_count,
        "ambiguous_signal_count": ambiguous_signal_count,
        "recovery_count": recovery_count,
        "completion_progress": completion_progress,
    }
    health_state, health_reasons = _classify_health(health_metrics, invariants)
    if health_state not in _HEALTH_STATES:
        raise ValueError("ambiguous health classification state")

    snapshot_basis = {
        "queue_id": queue_id,
        "timestamp": snapshot_timestamp,
        "work_items": work_items,
        "invariants": invariants,
        "health_metrics": health_metrics,
        "queue_health_state": health_state,
        "trace_linkage": trace_linkage,
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
        "trace_linkage": trace_linkage,
        "queue_health_state": health_state,
        "health_reason_codes": health_reasons,
        "health_metrics": health_metrics,
    }
