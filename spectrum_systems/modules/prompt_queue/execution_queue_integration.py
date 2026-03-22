"""Pure queue mutation integration for controlled prompt queue execution."""

from __future__ import annotations

from spectrum_systems.modules.prompt_queue.queue_artifact_io import (
    ArtifactValidationError,
    validate_queue_state,
    validate_work_item,
)
from spectrum_systems.modules.prompt_queue.queue_models import WorkItemStatus, iso_now, utc_now
from spectrum_systems.modules.prompt_queue.queue_state_machine import IllegalTransitionError, transition_work_item


class ExecutionQueueIntegrationError(ValueError):
    """Raised when controlled execution queue mutation fails closed."""


def _find_work_item_index(queue_state: dict, work_item_id: str) -> int:
    for idx, item in enumerate(queue_state.get("work_items", [])):
        if item.get("work_item_id") == work_item_id:
            return idx
    raise ExecutionQueueIntegrationError(f"Work item '{work_item_id}' not found in queue state.")


def _clone_queue(queue_state: dict) -> dict:
    queue_copy = dict(queue_state)
    queue_copy["work_items"] = [dict(item) for item in queue_state.get("work_items", [])]
    return queue_copy


def transition_to_executing(*, queue_state: dict, work_item_id: str, clock=utc_now) -> tuple[dict, dict]:
    queue_copy = _clone_queue(queue_state)
    idx = _find_work_item_index(queue_copy, work_item_id)
    target = dict(queue_copy["work_items"][idx])

    if target.get("execution_result_artifact_path"):
        raise ExecutionQueueIntegrationError("Duplicate execution prevented: execution_result_artifact_path already set.")

    if target["status"] != WorkItemStatus.RUNNABLE.value:
        raise ExecutionQueueIntegrationError("Execution entry requires work item status 'runnable'.")

    try:
        target = transition_work_item(target, WorkItemStatus.EXECUTING.value, clock=clock)
    except IllegalTransitionError as exc:
        raise ExecutionQueueIntegrationError(str(exc)) from exc

    queue_copy["work_items"][idx] = target
    queue_copy["updated_at"] = iso_now(clock)

    try:
        validate_work_item(target)
        validate_queue_state(queue_copy)
    except ArtifactValidationError as exc:
        raise ExecutionQueueIntegrationError(str(exc)) from exc

    return queue_copy, target


def finalize_execution(
    *,
    queue_state: dict,
    work_item_id: str,
    execution_result_artifact_path: str,
    execution_status: str,
    clock=utc_now,
) -> tuple[dict, dict]:
    queue_copy = _clone_queue(queue_state)
    idx = _find_work_item_index(queue_copy, work_item_id)
    target = dict(queue_copy["work_items"][idx])

    if target["status"] != WorkItemStatus.EXECUTING.value:
        raise ExecutionQueueIntegrationError("Finalization requires work item status 'executing'.")

    if target.get("execution_result_artifact_path"):
        raise ExecutionQueueIntegrationError("Duplicate finalization prevented: execution_result_artifact_path already set.")

    final_status_map = {
        "success": WorkItemStatus.EXECUTED_SUCCESS.value,
        "failure": WorkItemStatus.EXECUTED_FAILURE.value,
    }
    if execution_status not in final_status_map:
        raise ExecutionQueueIntegrationError(f"Unsupported execution_status: {execution_status}")

    try:
        target = transition_work_item(target, final_status_map[execution_status], clock=clock)
    except IllegalTransitionError as exc:
        raise ExecutionQueueIntegrationError(str(exc)) from exc

    target["execution_result_artifact_path"] = execution_result_artifact_path
    target["updated_at"] = iso_now(clock)

    queue_copy["work_items"][idx] = target
    queue_copy["updated_at"] = iso_now(clock)

    try:
        validate_work_item(target)
        validate_queue_state(queue_copy)
    except ArtifactValidationError as exc:
        raise ExecutionQueueIntegrationError(str(exc)) from exc

    return queue_copy, target
