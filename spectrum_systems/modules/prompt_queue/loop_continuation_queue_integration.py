"""Deterministic queue integration for loop continuation outcomes."""

from __future__ import annotations

from spectrum_systems.modules.prompt_queue.queue_artifact_io import (
    ArtifactValidationError,
    validate_loop_continuation,
    validate_queue_state,
    validate_work_item,
)
from spectrum_systems.modules.prompt_queue.queue_models import iso_now, utc_now


class LoopContinuationQueueIntegrationError(ValueError):
    """Raised when loop continuation queue mutation fails closed."""


def _find_work_item_index(queue_state: dict, work_item_id: str) -> int:
    for idx, item in enumerate(queue_state.get("work_items", [])):
        if item.get("work_item_id") == work_item_id:
            return idx
    raise LoopContinuationQueueIntegrationError(f"Work item '{work_item_id}' not found in queue state.")


def apply_loop_continuation_to_queue(
    *,
    queue_state: dict,
    work_item_id: str,
    loop_continuation_artifact: dict,
    loop_continuation_artifact_path: str,
    updated_queue_state: dict | None,
    spawned_child_work_item: dict | None,
    clock=utc_now,
) -> tuple[dict, dict]:
    try:
        validate_loop_continuation(loop_continuation_artifact)
    except ArtifactValidationError as exc:
        raise LoopContinuationQueueIntegrationError(str(exc)) from exc

    if loop_continuation_artifact.get("work_item_id") != work_item_id:
        raise LoopContinuationQueueIntegrationError("Loop continuation artifact work_item_id mismatch.")

    if not loop_continuation_artifact_path:
        raise LoopContinuationQueueIntegrationError("Missing loop continuation artifact path.")

    status = loop_continuation_artifact.get("continuation_status")
    if status == "continuation_failed":
        raise LoopContinuationQueueIntegrationError("Continuation failed; refusing queue mutation.")

    if status == "child_spawned":
        if updated_queue_state is None or spawned_child_work_item is None:
            raise LoopContinuationQueueIntegrationError("Child-spawn continuation requires updated queue and child work item.")
        queue_copy = dict(updated_queue_state)
        queue_copy["work_items"] = [dict(item) for item in updated_queue_state.get("work_items", [])]
    else:
        if updated_queue_state is not None or spawned_child_work_item is not None:
            raise LoopContinuationQueueIntegrationError(
                "Blocked/not-needed continuation must not carry spawned child queue mutation payloads."
            )
        queue_copy = dict(queue_state)
        queue_copy["work_items"] = [dict(item) for item in queue_state.get("work_items", [])]

    idx = _find_work_item_index(queue_copy, work_item_id)
    item = dict(queue_copy["work_items"][idx])

    if item.get("loop_continuation_artifact_path"):
        raise LoopContinuationQueueIntegrationError("Duplicate loop continuation attempt detected for work item.")

    if status == "child_spawned":
        child_id = loop_continuation_artifact.get("spawned_child_work_item_id")
        if not child_id:
            raise LoopContinuationQueueIntegrationError("Missing spawned_child_work_item_id for child_spawned status.")
        if child_id not in item.get("child_work_item_ids", []):
            raise LoopContinuationQueueIntegrationError(
                "Parent work item does not reference spawned child after child creation payload."
            )
    elif loop_continuation_artifact.get("spawned_child_work_item_id") is not None:
        raise LoopContinuationQueueIntegrationError("Blocked/not-needed continuation must not reference a spawned child.")

    item["loop_continuation_artifact_path"] = loop_continuation_artifact_path
    item["updated_at"] = iso_now(clock)
    queue_copy["work_items"][idx] = item
    queue_copy["updated_at"] = iso_now(clock)

    try:
        validate_work_item(item)
        validate_queue_state(queue_copy)
    except ArtifactValidationError as exc:
        raise LoopContinuationQueueIntegrationError(str(exc)) from exc

    return queue_copy, item
