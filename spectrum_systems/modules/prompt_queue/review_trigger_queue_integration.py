"""Pure deterministic queue integration for review trigger artifacts."""

from __future__ import annotations

from spectrum_systems.modules.prompt_queue.queue_artifact_io import (
    ArtifactValidationError,
    validate_queue_state,
    validate_work_item,
)
from spectrum_systems.modules.prompt_queue.queue_models import WorkItemStatus, iso_now, make_work_item, utc_now
from spectrum_systems.modules.prompt_queue.queue_state_machine import IllegalTransitionError, transition_work_item
from spectrum_systems.modules.prompt_queue.review_trigger_artifact_io import (
    ReviewTriggerArtifactValidationError,
    validate_review_trigger_artifact,
)


class ReviewTriggerQueueIntegrationError(ValueError):
    """Raised when review trigger queue integration fails closed."""


def _find_work_item_index(queue_state: dict, work_item_id: str) -> int:
    for idx, item in enumerate(queue_state.get("work_items", [])):
        if item.get("work_item_id") == work_item_id:
            return idx
    raise ReviewTriggerQueueIntegrationError(f"Work item '{work_item_id}' not found in queue state.")


def _make_review_child(parent: dict, review_trigger_artifact_path: str, clock=utc_now) -> dict:
    child_id = f"{parent['work_item_id']}.review.1"
    child = make_work_item(
        work_item_id=child_id,
        prompt_id=f"{parent['prompt_id']}:review:1",
        title=f"{parent['title']} [auto review 1]",
        priority=parent["priority"],
        risk_level=parent["risk_level"],
        repo=parent["repo"],
        branch=parent["branch"],
        scope_paths=parent["scope_paths"],
        parent_work_item_id=parent["work_item_id"],
        clock=clock,
    )
    child["status"] = WorkItemStatus.REVIEW_QUEUED.value
    child["generation_count"] = int(parent.get("generation_count") or 0)
    child["repair_loop_generation"] = int(parent.get("repair_loop_generation") or 0)
    child["execution_result_artifact_path"] = parent.get("execution_result_artifact_path")
    child["post_execution_decision_artifact_path"] = parent.get("post_execution_decision_artifact_path")
    child["loop_control_decision_artifact_path"] = parent.get("loop_control_decision_artifact_path")
    child["review_trigger_artifact_path"] = review_trigger_artifact_path
    child["spawned_from_execution_result_artifact_path"] = parent.get("execution_result_artifact_path")
    child["spawned_from_post_execution_decision_artifact_path"] = parent.get("post_execution_decision_artifact_path")
    child["spawned_from_loop_control_decision_artifact_path"] = parent.get("loop_control_decision_artifact_path")
    return child


def _assert_no_duplicate_spawn(queue_state: dict, parent_work_item_id: str, review_trigger_artifact_path: str) -> None:
    for item in queue_state.get("work_items", []):
        if item.get("parent_work_item_id") != parent_work_item_id:
            continue
        if item.get("review_trigger_artifact_path") == review_trigger_artifact_path:
            raise ReviewTriggerQueueIntegrationError(
                "Duplicate trigger detected: review trigger artifact already consumed by existing child."
            )
        if item.get("work_item_id") == f"{parent_work_item_id}.review.1":
            raise ReviewTriggerQueueIntegrationError(
                "Duplicate trigger detected: deterministic spawned review child already exists."
            )


def apply_review_trigger_to_queue(
    *,
    queue_state: dict,
    work_item_id: str,
    review_trigger_artifact: dict,
    review_trigger_artifact_path: str,
    clock=utc_now,
) -> tuple[dict, dict, dict | None, dict]:
    queue_copy = dict(queue_state)
    queue_copy["work_items"] = [dict(item) for item in queue_state.get("work_items", [])]

    try:
        validate_review_trigger_artifact(review_trigger_artifact)
    except ReviewTriggerArtifactValidationError as exc:
        raise ReviewTriggerQueueIntegrationError(str(exc)) from exc

    idx = _find_work_item_index(queue_copy, work_item_id)
    target = dict(queue_copy["work_items"][idx])

    if review_trigger_artifact.get("work_item_id") != work_item_id:
        raise ReviewTriggerQueueIntegrationError("Review trigger work_item_id does not match target work item.")

    if review_trigger_artifact.get("parent_work_item_id") != target.get("parent_work_item_id"):
        raise ReviewTriggerQueueIntegrationError("Review trigger parent_work_item_id mismatch.")

    if review_trigger_artifact.get("post_execution_decision_artifact_path") != target.get(
        "post_execution_decision_artifact_path"
    ):
        raise ReviewTriggerQueueIntegrationError("Review trigger post_execution_decision_artifact_path mismatch.")

    if review_trigger_artifact.get("execution_result_artifact_path") != target.get("execution_result_artifact_path"):
        raise ReviewTriggerQueueIntegrationError("Review trigger execution_result_artifact_path mismatch.")

    if review_trigger_artifact.get("loop_control_decision_artifact_path") != target.get("loop_control_decision_artifact_path"):
        raise ReviewTriggerQueueIntegrationError("Review trigger loop_control_decision_artifact_path mismatch.")

    if target.get("review_trigger_artifact_path"):
        raise ReviewTriggerQueueIntegrationError("Duplicate trigger detected: work item already linked to review trigger artifact.")

    trigger_status = review_trigger_artifact["trigger_status"]
    if trigger_status == "review_triggered":
        if target.get("status") != WorkItemStatus.REVIEW_REQUIRED.value:
            raise ReviewTriggerQueueIntegrationError("Invalid state: review_triggered requires work item status review_required.")
        try:
            target = transition_work_item(target, WorkItemStatus.REVIEW_TRIGGERED.value, clock=clock)
        except IllegalTransitionError as exc:
            raise ReviewTriggerQueueIntegrationError(str(exc)) from exc
    elif trigger_status == "no_review_needed":
        if target.get("status") != WorkItemStatus.COMPLETE.value:
            raise ReviewTriggerQueueIntegrationError("Invalid state: no_review_needed requires work item status complete.")
    elif trigger_status == "blocked_no_trigger":
        if target.get("status") not in {WorkItemStatus.REVIEW_REQUIRED.value, WorkItemStatus.REENTRY_BLOCKED.value}:
            raise ReviewTriggerQueueIntegrationError(
                "Invalid state: blocked_no_trigger requires work item status review_required or reentry_blocked."
            )
        try:
            target = transition_work_item(target, WorkItemStatus.BLOCKED.value, clock=clock)
        except IllegalTransitionError as exc:
            raise ReviewTriggerQueueIntegrationError(str(exc)) from exc
    else:
        raise ReviewTriggerQueueIntegrationError(f"Unsupported trigger_status: {trigger_status}")

    spawned_child = None
    target.setdefault("child_work_item_ids", [])
    target["review_trigger_artifact_path"] = review_trigger_artifact_path
    target["updated_at"] = iso_now(clock)

    if trigger_status == "review_triggered":
        _assert_no_duplicate_spawn(queue_copy, work_item_id, review_trigger_artifact_path)
        spawned_child = _make_review_child(target, review_trigger_artifact_path, clock=clock)
        target["child_work_item_ids"] = [*target["child_work_item_ids"], spawned_child["work_item_id"]]

    queue_copy["work_items"][idx] = target
    if spawned_child is not None:
        queue_copy["work_items"].append(spawned_child)
    queue_copy["updated_at"] = iso_now(clock)

    updated_trigger = dict(review_trigger_artifact)
    updated_trigger["spawned_review_work_item_id"] = spawned_child.get("work_item_id") if spawned_child else None

    try:
        validate_work_item(target)
        if spawned_child is not None:
            validate_work_item(spawned_child)
        validate_queue_state(queue_copy)
        validate_review_trigger_artifact(updated_trigger)
    except (ArtifactValidationError, ReviewTriggerArtifactValidationError) as exc:
        raise ReviewTriggerQueueIntegrationError(str(exc)) from exc

    return queue_copy, target, spawned_child, updated_trigger
