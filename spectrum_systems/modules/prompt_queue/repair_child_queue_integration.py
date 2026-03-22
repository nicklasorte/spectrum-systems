"""Pure queue mutation for governed repair child work-item spawning."""

from __future__ import annotations

from spectrum_systems.modules.prompt_queue.queue_artifact_io import validate_queue_state, validate_work_item
from spectrum_systems.modules.prompt_queue.queue_models import WorkItemStatus, iso_now, utc_now
from spectrum_systems.modules.prompt_queue.queue_state_machine import transition_work_item
from spectrum_systems.modules.prompt_queue.repair_child_creator import (
    RepairChildCreationError,
    build_repair_child_work_item,
)


class RepairChildQueueIntegrationError(ValueError):
    """Raised when queue-level repair child integration fails closed."""


def _find_work_item_index(queue_state: dict, work_item_id: str) -> int:
    for idx, item in enumerate(queue_state.get("work_items", [])):
        if item.get("work_item_id") == work_item_id:
            return idx
    raise RepairChildQueueIntegrationError(f"Parent work item '{work_item_id}' not found in queue state.")


def _detect_duplicate_spawn(queue_state: dict, parent_work_item_id: str, repair_prompt_artifact_path: str) -> None:
    for work_item in queue_state.get("work_items", []):
        if work_item.get("parent_work_item_id") != parent_work_item_id:
            continue
        if work_item.get("spawned_from_repair_prompt_artifact_path") == repair_prompt_artifact_path:
            raise RepairChildQueueIntegrationError(
                "Duplicate child spawn detected: repair prompt artifact has already spawned a child work item."
            )


def spawn_repair_child_in_queue(
    *,
    queue_state: dict,
    parent_work_item_id: str,
    repair_prompt_artifact: dict,
    repair_prompt_artifact_path: str,
    clock=utc_now,
) -> tuple[dict, dict, dict]:
    """Create a child work item from a repair prompt and apply deterministic queue updates."""

    queue_copy = dict(queue_state)
    queue_copy["work_items"] = [dict(item) for item in queue_state.get("work_items", [])]

    parent_idx = _find_work_item_index(queue_copy, parent_work_item_id)
    parent = queue_copy["work_items"][parent_idx]

    _detect_duplicate_spawn(queue_copy, parent_work_item_id, repair_prompt_artifact_path)

    try:
        child = build_repair_child_work_item(
            parent_work_item=parent,
            repair_prompt_artifact=repair_prompt_artifact,
            repair_prompt_artifact_path=repair_prompt_artifact_path,
            clock=clock,
        )
    except RepairChildCreationError as exc:
        raise RepairChildQueueIntegrationError(str(exc)) from exc

    parent_updated = dict(parent)
    parent_updated.setdefault("child_work_item_ids", [])
    parent_updated["child_work_item_ids"] = [*parent_updated["child_work_item_ids"], child["work_item_id"]]
    if parent_updated["status"] == WorkItemStatus.REPAIR_PROMPT_GENERATED.value:
        parent_updated = transition_work_item(
            parent_updated,
            WorkItemStatus.REPAIR_CHILD_CREATED.value,
            clock=clock,
        )
    else:
        parent_updated["updated_at"] = iso_now(clock)

    queue_copy["work_items"][parent_idx] = parent_updated
    queue_copy["work_items"].append(child)
    queue_copy["updated_at"] = iso_now(clock)

    validate_work_item(parent_updated)
    validate_work_item(child)
    validate_queue_state(queue_copy)
    return queue_copy, parent_updated, child
