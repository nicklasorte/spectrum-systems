"""Pure queue mutation for prompt queue execution gating decisions."""

from __future__ import annotations

from spectrum_systems.modules.prompt_queue.execution_gating_artifact_io import (
    ExecutionGatingArtifactValidationError,
    validate_execution_gating_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.queue_artifact_io import (
    ArtifactValidationError,
    validate_queue_state,
    validate_work_item,
)
from spectrum_systems.modules.prompt_queue.queue_models import WorkItemStatus, iso_now, utc_now
from spectrum_systems.modules.prompt_queue.queue_state_machine import IllegalTransitionError, transition_work_item


class ExecutionGatingQueueIntegrationError(ValueError):
    """Raised when execution gating queue integration fails closed."""


def _find_work_item_index(queue_state: dict, work_item_id: str) -> int:
    for idx, item in enumerate(queue_state.get("work_items", [])):
        if item.get("work_item_id") == work_item_id:
            return idx
    raise ExecutionGatingQueueIntegrationError(f"Work item '{work_item_id}' not found in queue state.")


def _decision_to_status(decision_status: str) -> str:
    mapping = {
        "runnable": WorkItemStatus.RUNNABLE.value,
        "approval_required": WorkItemStatus.APPROVAL_REQUIRED.value,
        "blocked": WorkItemStatus.BLOCKED.value,
    }
    if decision_status not in mapping:
        raise ExecutionGatingQueueIntegrationError(f"Unsupported decision_status: {decision_status}")
    return mapping[decision_status]


def apply_execution_gating_decision_to_queue(
    *,
    queue_state: dict,
    work_item_id: str,
    gating_decision_artifact: dict,
    gating_decision_artifact_path: str,
    clock=utc_now,
) -> tuple[dict, dict]:
    queue_copy = dict(queue_state)
    queue_copy["work_items"] = [dict(item) for item in queue_state.get("work_items", [])]

    try:
        validate_execution_gating_decision_artifact(gating_decision_artifact)
    except ExecutionGatingArtifactValidationError as exc:
        raise ExecutionGatingQueueIntegrationError(str(exc)) from exc

    idx = _find_work_item_index(queue_copy, work_item_id)
    target = dict(queue_copy["work_items"][idx])

    if gating_decision_artifact.get("work_item_id") != work_item_id:
        raise ExecutionGatingQueueIntegrationError("Gating decision work_item_id does not match target work item.")

    target_status = _decision_to_status(gating_decision_artifact["decision_status"])

    try:
        if target["status"] == WorkItemStatus.REPAIR_CHILD_CREATED.value:
            target = transition_work_item(target, WorkItemStatus.EXECUTION_GATED.value, clock=clock)
        elif target["status"] != WorkItemStatus.EXECUTION_GATED.value:
            raise ExecutionGatingQueueIntegrationError(
                "Work item must be in 'repair_child_created' or 'execution_gated' before applying a gating decision."
            )

        target = transition_work_item(target, target_status, clock=clock)
    except IllegalTransitionError as exc:
        raise ExecutionGatingQueueIntegrationError(str(exc)) from exc

    target["gating_decision_artifact_path"] = gating_decision_artifact_path
    target["updated_at"] = iso_now(clock)

    queue_copy["work_items"][idx] = target
    queue_copy["updated_at"] = iso_now(clock)

    try:
        validate_work_item(target)
        validate_queue_state(queue_copy)
    except ArtifactValidationError as exc:
        raise ExecutionGatingQueueIntegrationError(str(exc)) from exc

    return queue_copy, target
