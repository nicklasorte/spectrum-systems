"""Pure deterministic mapping from post-execution decision artifacts to next-step queue actions."""

from __future__ import annotations

from dataclasses import dataclass

from spectrum_systems.modules.prompt_queue.next_step_action_artifact_io import validate_next_step_action_artifact
from spectrum_systems.modules.prompt_queue.post_execution_artifact_io import (
    PostExecutionArtifactValidationError,
    validate_post_execution_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.queue_artifact_io import ArtifactValidationError, validate_work_item
from spectrum_systems.modules.prompt_queue.queue_models import iso_now, utc_now


class NextStepOrchestrationError(ValueError):
    """Raised when next-step orchestration cannot proceed safely."""


@dataclass(frozen=True)
class NextStepOrchestrationConfig:
    generator_version: str = "prompt_queue_next_step_orchestrator.v1"


_DECISION_TO_ACTION = {
    "complete": ("marked_complete", "marked_complete_from_post_execution_complete"),
    "review_required": ("spawn_review", "spawn_review_from_post_execution_review_required"),
    "reentry_eligible": ("spawn_reentry_child", "spawn_reentry_child_from_post_execution_reentry_eligible"),
    "reentry_blocked": ("blocked_no_action", "blocked_no_action_from_post_execution_reentry_blocked"),
}


def determine_next_step_action(
    *,
    work_item: dict,
    post_execution_decision_artifact: dict,
    post_execution_decision_artifact_path: str,
    execution_result_artifact_path: str,
    source_queue_state_path: str | None,
    config: NextStepOrchestrationConfig = NextStepOrchestrationConfig(),
    clock=utc_now,
) -> dict:
    try:
        validate_work_item(work_item)
    except ArtifactValidationError as exc:
        raise NextStepOrchestrationError(f"Malformed work item: {exc}") from exc

    try:
        validate_post_execution_decision_artifact(post_execution_decision_artifact)
    except PostExecutionArtifactValidationError as exc:
        raise NextStepOrchestrationError(f"Malformed post-execution decision artifact: {exc}") from exc

    if post_execution_decision_artifact.get("work_item_id") != work_item.get("work_item_id"):
        raise NextStepOrchestrationError("Post-execution decision work_item_id does not match work item.")

    if post_execution_decision_artifact.get("parent_work_item_id") != work_item.get("parent_work_item_id"):
        raise NextStepOrchestrationError("Post-execution decision parent_work_item_id does not match work item lineage.")

    if post_execution_decision_artifact_path != work_item.get("post_execution_decision_artifact_path"):
        raise NextStepOrchestrationError(
            "Post-execution decision artifact path mismatch with work item lineage."
        )

    if execution_result_artifact_path != work_item.get("execution_result_artifact_path"):
        raise NextStepOrchestrationError("Execution result artifact path mismatch with work item lineage.")

    if post_execution_decision_artifact.get("execution_result_artifact_path") != execution_result_artifact_path:
        raise NextStepOrchestrationError(
            "Post-execution decision execution_result_artifact_path does not match input lineage."
        )

    decision_status = post_execution_decision_artifact.get("decision_status")
    if decision_status not in _DECISION_TO_ACTION:
        raise NextStepOrchestrationError(f"Unsupported decision_status for next-step orchestration: {decision_status}")

    action_status, action_reason_code = _DECISION_TO_ACTION[decision_status]
    artifact = {
        "next_step_action_artifact_id": f"nextstep-{work_item['work_item_id']}-{iso_now(clock)}",
        "work_item_id": work_item["work_item_id"],
        "parent_work_item_id": work_item.get("parent_work_item_id"),
        "post_execution_decision_artifact_path": post_execution_decision_artifact_path,
        "execution_result_artifact_path": execution_result_artifact_path,
        "action_status": action_status,
        "action_reason_code": action_reason_code,
        "decision_status": decision_status,
        "generated_at": iso_now(clock),
        "generator_version": config.generator_version,
        "spawned_work_item_id": None,
        "blocking_conditions": list(post_execution_decision_artifact.get("blocking_conditions") or []),
        "warnings": list(post_execution_decision_artifact.get("warnings") or []),
        "source_queue_state_path": source_queue_state_path,
    }
    validate_next_step_action_artifact(artifact)
    return artifact
