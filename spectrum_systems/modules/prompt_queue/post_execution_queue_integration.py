"""Post-execution integration with legacy queue mutation and transition receipt surfaces."""

from __future__ import annotations

from spectrum_systems.modules.prompt_queue.post_execution_artifact_io import (
    PostExecutionArtifactValidationError,
    validate_post_execution_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.prompt_queue_transition_artifact_io import (
    PromptQueueTransitionArtifactValidationError,
    validate_prompt_queue_transition_decision_artifact,
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


def _transition_from_post_execution(post_execution_decision_artifact: dict) -> dict:
    decision_status = post_execution_decision_artifact.get("decision_status")
    mapping = {
        "complete": "continue",
        "review_required": "request_review",
        "reentry_eligible": "reenter_with_findings",
        "reentry_blocked": "block",
    }
    transition_action = mapping.get(decision_status)
    if not transition_action:
        raise PostExecutionQueueIntegrationError(f"Unsupported decision_status: {decision_status}")

    return {
        "transition_decision_id": f"compat-postexec-{post_execution_decision_artifact.get('post_execution_decision_artifact_id', 'unknown')}",
        "step_id": "step-001",
        "queue_id": None,
        "trace_linkage": post_execution_decision_artifact.get("work_item_id") or "unknown",
        "source_decision_ref": post_execution_decision_artifact.get("post_execution_decision_artifact_id")
        or post_execution_decision_artifact.get("execution_result_artifact_path")
        or "unknown",
        "transition_action": transition_action,
        "transition_status": "blocked" if transition_action == "block" else "allowed",
        "reason_codes": ["block_invalid_report_fail_closed"] if transition_action == "block" else ["warn_findings_request_review"],
        "blocking_reasons": ["unsupported_decision"] if transition_action == "block" else [],
        "derived_from_artifacts": [post_execution_decision_artifact.get("execution_result_artifact_path") or "unknown"],
        "timestamp": post_execution_decision_artifact.get("generated_at") or "2026-03-28T00:00:00Z",
    }


def emit_post_execution_transition_receipt(
    *,
    queue_state: dict,
    transition_decision_artifact: dict,
    transition_decision_artifact_path: str,
) -> dict:
    try:
        validate_queue_state(queue_state)
    except ArtifactValidationError as exc:
        raise PostExecutionQueueIntegrationError(str(exc)) from exc

    try:
        validate_prompt_queue_transition_decision_artifact(transition_decision_artifact)
    except PromptQueueTransitionArtifactValidationError as exc:
        raise PostExecutionQueueIntegrationError(str(exc)) from exc

    return {
        "integration_type": "post_execution_transition",
        "queue_mutation_performed": False,
        "transition_decision_artifact_path": transition_decision_artifact_path,
        "transition_action": transition_decision_artifact["transition_action"],
        "transition_status": transition_decision_artifact["transition_status"],
        "source_decision_ref": transition_decision_artifact["source_decision_ref"],
    }


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

    transition = _transition_from_post_execution(post_execution_decision_artifact)
    emit_post_execution_transition_receipt(
        queue_state=queue_copy,
        transition_decision_artifact=transition,
        transition_decision_artifact_path=post_execution_decision_artifact_path,
    )

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
