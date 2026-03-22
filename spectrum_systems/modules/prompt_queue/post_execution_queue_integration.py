"""Pure queue mutation for prompt queue post-execution decisions."""

from __future__ import annotations

from spectrum_systems.modules.prompt_queue.post_execution_artifact_io import (
    PostExecutionArtifactValidationError,
    validate_post_execution_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.queue_artifact_io import (
    ArtifactValidationError,
    validate_queue_state,
    validate_work_item,
)
from spectrum_systems.modules.prompt_queue.queue_models import WorkItemStatus, iso_now, utc_now
from spectrum_systems.modules.prompt_queue.queue_state_machine import IllegalTransitionError, transition_work_item


class PostExecutionQueueIntegrationError(ValueError):
    """Raised when post-execution queue integration fails closed."""


def _find_work_item_index(queue_state: dict, work_item_id: str) -> int:
    for idx, item in enumerate(queue_state.get("work_items", [])):
        if item.get("work_item_id") == work_item_id:
            return idx
    raise PostExecutionQueueIntegrationError(f"Work item '{work_item_id}' not found in queue state.")


def _decision_to_status(decision_status: str) -> str:
    mapping = {
        "complete": WorkItemStatus.COMPLETE.value,
        "review_required": WorkItemStatus.REVIEW_REQUIRED.value,
        "reentry_blocked": WorkItemStatus.REENTRY_BLOCKED.value,
        "reentry_eligible": WorkItemStatus.REENTRY_ELIGIBLE.value,
    }
    if decision_status not in mapping:
        raise PostExecutionQueueIntegrationError(f"Unsupported decision_status: {decision_status}")
    return mapping[decision_status]


def apply_post_execution_decision_to_queue(
    *,
    queue_state: dict,
    work_item_id: str,
    post_execution_decision_artifact: dict,
    post_execution_decision_artifact_path: str,
    clock=utc_now,
) -> tuple[dict, dict]:
    queue_copy = dict(queue_state)
    queue_copy["work_items"] = [dict(item) for item in queue_state.get("work_items", [])]

    try:
        validate_post_execution_decision_artifact(post_execution_decision_artifact)
    except PostExecutionArtifactValidationError as exc:
        raise PostExecutionQueueIntegrationError(str(exc)) from exc

    idx = _find_work_item_index(queue_copy, work_item_id)
    target = dict(queue_copy["work_items"][idx])

    if post_execution_decision_artifact.get("work_item_id") != work_item_id:
        raise PostExecutionQueueIntegrationError("Post-execution decision work_item_id does not match target work item.")

    expected_execution_status = (
        "success" if target.get("status") == WorkItemStatus.EXECUTED_SUCCESS.value else "failure"
    )
    if target.get("status") not in {WorkItemStatus.EXECUTED_SUCCESS.value, WorkItemStatus.EXECUTED_FAILURE.value}:
        raise PostExecutionQueueIntegrationError(
            "Work item must be in 'executed_success' or 'executed_failure' before applying a post-execution decision."
        )

    if post_execution_decision_artifact.get("execution_status") != expected_execution_status:
        raise PostExecutionQueueIntegrationError("Post-execution decision execution_status does not match work item status.")

    if post_execution_decision_artifact.get("execution_result_artifact_path") != target.get("execution_result_artifact_path"):
        raise PostExecutionQueueIntegrationError("Post-execution decision execution_result_artifact_path mismatch.")

    if post_execution_decision_artifact.get("gating_decision_artifact_path") != target.get("gating_decision_artifact_path"):
        raise PostExecutionQueueIntegrationError("Post-execution decision gating_decision_artifact_path mismatch.")

    if post_execution_decision_artifact.get("repair_prompt_artifact_path") != target.get("repair_prompt_artifact_path"):
        raise PostExecutionQueueIntegrationError("Post-execution decision repair_prompt_artifact_path mismatch.")

    target_status = _decision_to_status(post_execution_decision_artifact["decision_status"])

    try:
        target = transition_work_item(target, target_status, clock=clock)
    except IllegalTransitionError as exc:
        raise PostExecutionQueueIntegrationError(str(exc)) from exc

    target["post_execution_decision_artifact_path"] = post_execution_decision_artifact_path
    target["updated_at"] = iso_now(clock)

    queue_copy["work_items"][idx] = target
    queue_copy["updated_at"] = iso_now(clock)

    try:
        validate_work_item(target)
        validate_queue_state(queue_copy)
    except ArtifactValidationError as exc:
        raise PostExecutionQueueIntegrationError(str(exc)) from exc

    return queue_copy, target
