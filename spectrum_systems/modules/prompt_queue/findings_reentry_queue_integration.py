"""Deterministic queue integration for findings-to-repair reentry artifacts."""

from __future__ import annotations

from spectrum_systems.modules.prompt_queue.queue_artifact_io import validate_queue_state, validate_work_item
from spectrum_systems.modules.prompt_queue.queue_models import WorkItemStatus, iso_now, utc_now
from spectrum_systems.modules.prompt_queue.queue_state_machine import transition_work_item


class FindingsReentryQueueIntegrationError(ValueError):
    """Raised when findings reentry queue mutation fails closed."""


def _find_work_item_index(queue_state: dict, work_item_id: str) -> int:
    for idx, item in enumerate(queue_state.get("work_items", [])):
        if item.get("work_item_id") == work_item_id:
            return idx
    raise FindingsReentryQueueIntegrationError(f"Work item '{work_item_id}' not found in queue state.")


def apply_findings_reentry_to_queue(
    *,
    queue_state: dict,
    work_item_id: str,
    findings_reentry_artifact_path: str,
    repair_prompt_artifact_path: str,
    clock=utc_now,
) -> tuple[dict, dict]:
    queue_copy = dict(queue_state)
    queue_copy["work_items"] = [dict(item) for item in queue_state.get("work_items", [])]
    idx = _find_work_item_index(queue_copy, work_item_id)
    item = dict(queue_copy["work_items"][idx])

    if item.get("findings_reentry_artifact_path"):
        raise FindingsReentryQueueIntegrationError("Duplicate findings reentry attempt detected for work item.")
    if item.get("repair_prompt_artifact_path"):
        raise FindingsReentryQueueIntegrationError("Work item already has repair_prompt_artifact_path; duplicate reentry denied.")
    if item.get("status") != WorkItemStatus.FINDINGS_PARSED.value:
        raise FindingsReentryQueueIntegrationError(
            f"Invalid state '{item.get('status')}' for findings-to-repair reentry."
        )
    if not findings_reentry_artifact_path:
        raise FindingsReentryQueueIntegrationError("Missing findings reentry artifact path; queue update denied.")
    if not repair_prompt_artifact_path:
        raise FindingsReentryQueueIntegrationError("Missing repair prompt artifact path; queue update denied.")

    item["findings_reentry_artifact_path"] = findings_reentry_artifact_path
    item["repair_prompt_artifact_path"] = repair_prompt_artifact_path
    item = transition_work_item(item, WorkItemStatus.REPAIR_PROMPT_GENERATED.value, clock=clock)

    queue_copy["work_items"][idx] = item
    queue_copy["updated_at"] = iso_now(clock)

    validate_work_item(item)
    validate_queue_state(queue_copy)
    return queue_copy, item
