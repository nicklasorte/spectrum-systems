"""Deterministic state transitions for prompt queue work items."""

from __future__ import annotations

from typing import Callable

from spectrum_systems.modules.prompt_queue.queue_models import WorkItemStatus, iso_now, utc_now


class IllegalTransitionError(ValueError):
    """Raised when an illegal state transition is requested."""


_ALLOWED_TRANSITIONS = {
    WorkItemStatus.QUEUED.value: {WorkItemStatus.REVIEW_QUEUED.value, WorkItemStatus.BLOCKED.value},
    WorkItemStatus.REVIEW_QUEUED.value: {WorkItemStatus.REVIEW_RUNNING.value, WorkItemStatus.BLOCKED.value},
    WorkItemStatus.REVIEW_RUNNING.value: {
        WorkItemStatus.REVIEW_COMPLETE.value,
        WorkItemStatus.REVIEW_PROVIDER_FAILED.value,
        WorkItemStatus.BLOCKED.value,
    },
    WorkItemStatus.REVIEW_PROVIDER_FAILED.value: {
        WorkItemStatus.REVIEW_FALLBACK_RUNNING.value,
        WorkItemStatus.BLOCKED.value,
    },
    WorkItemStatus.REVIEW_FALLBACK_RUNNING.value: {
        WorkItemStatus.REVIEW_COMPLETE.value,
        WorkItemStatus.BLOCKED.value,
    },
    WorkItemStatus.REVIEW_COMPLETE.value: {WorkItemStatus.FINDINGS_PARSED.value},
    WorkItemStatus.FINDINGS_PARSED.value: {WorkItemStatus.REPAIR_PROMPT_GENERATED.value},
    WorkItemStatus.REPAIR_PROMPT_GENERATED.value: {WorkItemStatus.REPAIR_CHILD_CREATED.value},
    WorkItemStatus.REPAIR_CHILD_CREATED.value: {
        WorkItemStatus.EXECUTION_GATED.value,
        WorkItemStatus.BLOCKED.value,
    },
    WorkItemStatus.EXECUTION_GATED.value: {
        WorkItemStatus.RUNNABLE.value,
        WorkItemStatus.APPROVAL_REQUIRED.value,
        WorkItemStatus.BLOCKED.value,
    },
    WorkItemStatus.APPROVAL_REQUIRED.value: {
        WorkItemStatus.RUNNABLE.value,
        WorkItemStatus.BLOCKED.value,
    },
    WorkItemStatus.RUNNABLE.value: {WorkItemStatus.EXECUTING.value},
    WorkItemStatus.EXECUTING.value: {
        WorkItemStatus.EXECUTED_SUCCESS.value,
        WorkItemStatus.EXECUTED_FAILURE.value,
    },
    WorkItemStatus.EXECUTED_SUCCESS.value: {WorkItemStatus.COMPLETE.value},
    WorkItemStatus.EXECUTED_FAILURE.value: {
        WorkItemStatus.REVIEW_REQUIRED.value,
        WorkItemStatus.REENTRY_BLOCKED.value,
        WorkItemStatus.REENTRY_ELIGIBLE.value,
        WorkItemStatus.BLOCKED.value,
    },
    WorkItemStatus.REVIEW_REQUIRED.value: {
        WorkItemStatus.REVIEW_TRIGGERED.value,
        WorkItemStatus.BLOCKED.value,
    },
    WorkItemStatus.REENTRY_BLOCKED.value: {WorkItemStatus.BLOCKED.value},
    WorkItemStatus.REVIEW_TRIGGERED.value: {WorkItemStatus.REVIEW_INVOKING.value, WorkItemStatus.BLOCKED.value},
    WorkItemStatus.REVIEW_INVOKING.value: {
        WorkItemStatus.REVIEW_INVOCATION_SUCCEEDED.value,
        WorkItemStatus.REVIEW_INVOCATION_FAILED.value,
        WorkItemStatus.BLOCKED.value,
    },
    WorkItemStatus.REVIEW_INVOCATION_SUCCEEDED.value: set(),
    WorkItemStatus.REVIEW_INVOCATION_FAILED.value: set(),
    WorkItemStatus.REENTRY_ELIGIBLE.value: set(),
    WorkItemStatus.COMPLETE.value: set(),
    WorkItemStatus.BLOCKED.value: set(),
}


Clock = Callable


def transition_work_item(
    work_item: dict,
    to_status: str,
    *,
    clock: Clock = utc_now,
) -> dict:
    from_status = work_item["status"]
    allowed = _ALLOWED_TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        raise IllegalTransitionError(
            f"Illegal transition from '{from_status}' to '{to_status}'. Allowed={sorted(allowed)}"
        )
    updated = dict(work_item)
    updated["status"] = to_status
    updated["updated_at"] = iso_now(clock)
    return updated
