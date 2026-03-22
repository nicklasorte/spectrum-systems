"""Deterministic queue integration for review parsing handoff artifacts."""

from __future__ import annotations

from spectrum_systems.modules.prompt_queue.queue_artifact_io import validate_queue_state, validate_work_item
from spectrum_systems.modules.prompt_queue.queue_models import WorkItemStatus, iso_now, utc_now
from spectrum_systems.modules.prompt_queue.queue_state_machine import transition_work_item


class ReviewParsingHandoffQueueIntegrationError(ValueError):
    """Raised when queue mutation for parsing handoff fails closed."""


def _find_work_item_index(queue_state: dict, work_item_id: str) -> int:
    for idx, item in enumerate(queue_state.get("work_items", [])):
        if item.get("work_item_id") == work_item_id:
            return idx
    raise ReviewParsingHandoffQueueIntegrationError(f"Work item '{work_item_id}' not found in queue state.")


def apply_review_parsing_handoff_to_queue(
    *,
    queue_state: dict,
    work_item_id: str,
    findings_artifact_path: str,
    review_parsing_handoff_artifact_path: str,
    clock=utc_now,
) -> tuple[dict, dict]:
    queue_copy = dict(queue_state)
    queue_copy["work_items"] = [dict(item) for item in queue_state.get("work_items", [])]
    idx = _find_work_item_index(queue_copy, work_item_id)
    item = dict(queue_copy["work_items"][idx])

    if item.get("review_parsing_handoff_artifact_path"):
        raise ReviewParsingHandoffQueueIntegrationError("Duplicate handoff attempt detected for work item.")
    if item.get("status") != WorkItemStatus.REVIEW_INVOCATION_SUCCEEDED.value:
        raise ReviewParsingHandoffQueueIntegrationError(
            f"Invalid state '{item.get('status')}' for review parsing handoff."
        )
    if not findings_artifact_path:
        raise ReviewParsingHandoffQueueIntegrationError("Missing findings artifact path; handoff cannot continue.")

    item["findings_artifact_path"] = findings_artifact_path
    item["review_parsing_handoff_artifact_path"] = review_parsing_handoff_artifact_path
    item = transition_work_item(item, WorkItemStatus.FINDINGS_PARSED.value, clock=clock)

    queue_copy["work_items"][idx] = item
    queue_copy["updated_at"] = iso_now(clock)

    validate_work_item(item)
    validate_queue_state(queue_copy)
    return queue_copy, item
