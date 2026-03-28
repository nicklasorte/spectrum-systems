"""Deterministic next-step orchestration supporting transition and legacy post-execution inputs."""

from __future__ import annotations

from dataclasses import dataclass

from spectrum_systems.modules.prompt_queue.next_step_action_artifact_io import validate_next_step_action_artifact
from spectrum_systems.modules.prompt_queue.post_execution_artifact_io import (
    PostExecutionArtifactValidationError,
    validate_post_execution_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.prompt_queue_transition_artifact_io import (
    PromptQueueTransitionArtifactValidationError,
    validate_prompt_queue_transition_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.queue_artifact_io import ArtifactValidationError, validate_work_item
from spectrum_systems.modules.prompt_queue.queue_models import iso_now, utc_now


class NextStepOrchestrationError(ValueError):
    """Raised when next-step orchestration cannot proceed safely."""


@dataclass(frozen=True)
class NextStepOrchestrationConfig:
    generator_version: str = "prompt_queue_next_step_orchestrator.v2"


_ACTION_MAP = {
    "continue": ("marked_complete", "marked_complete_from_post_execution_complete", "complete"),
    "request_review": ("spawn_review", "spawn_review_from_post_execution_review_required", "review_required"),
    "reenter_with_findings": (
        "spawn_reentry_child",
        "spawn_reentry_child_from_post_execution_reentry_eligible",
        "reentry_eligible",
    ),
    "retry_allowed": (
        "spawn_reentry_child",
        "spawn_reentry_child_from_post_execution_reentry_eligible",
        "reentry_eligible",
    ),
    "block": ("blocked_no_action", "blocked_no_action_from_post_execution_reentry_blocked", "reentry_blocked"),
}

_DECISION_TO_ACTION = {
    "complete": "continue",
    "review_required": "request_review",
    "reentry_eligible": "reenter_with_findings",
    "reentry_blocked": "block",
}


def _normalize_transition_from_legacy(
    *,
    work_item: dict,
    post_execution_decision_artifact: dict,
    post_execution_decision_artifact_path: str,
) -> tuple[dict, str, str]:
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
        raise NextStepOrchestrationError("Post-execution decision artifact path mismatch with work item lineage.")

    execution_result_artifact_path = work_item.get("execution_result_artifact_path")
    if not execution_result_artifact_path:
        raise NextStepOrchestrationError("Execution result artifact path mismatch with work item lineage.")

    if post_execution_decision_artifact.get("execution_result_artifact_path") != execution_result_artifact_path:
        raise NextStepOrchestrationError(
            "Post-execution decision execution_result_artifact_path does not match input lineage."
        )

    decision_status = post_execution_decision_artifact.get("decision_status")
    if decision_status not in _DECISION_TO_ACTION:
        raise NextStepOrchestrationError(f"Unsupported decision_status for next-step orchestration: {decision_status}")

    transition_action = _DECISION_TO_ACTION[decision_status]
    transition = {
        "transition_decision_id": f"compat-{post_execution_decision_artifact.get('post_execution_decision_artifact_id', 'unknown')}",
        "step_id": "step-001",
        "queue_id": None,
        "trace_linkage": work_item.get("work_item_id") or "unknown",
        "source_decision_ref": post_execution_decision_artifact.get("post_execution_decision_artifact_id")
        or post_execution_decision_artifact_path,
        "transition_action": transition_action,
        "transition_status": "blocked" if transition_action == "block" else "allowed",
        "reason_codes": [
            "block_invalid_report_fail_closed" if transition_action == "block" else "warn_findings_request_review"
        ],
        "blocking_reasons": ["unsupported_decision"] if transition_action == "block" else [],
        "derived_from_artifacts": [execution_result_artifact_path],
        "timestamp": post_execution_decision_artifact.get("generated_at") or iso_now(utc_now),
    }
    return transition, post_execution_decision_artifact_path, execution_result_artifact_path


def determine_next_step_action(
    *,
    transition_decision_artifact: dict | None = None,
    transition_decision_artifact_path: str | None = None,
    source_queue_state_path: str | None,
    config: NextStepOrchestrationConfig = NextStepOrchestrationConfig(),
    clock=utc_now,
    work_item: dict | None = None,
    post_execution_decision_artifact: dict | None = None,
    post_execution_decision_artifact_path: str | None = None,
    execution_result_artifact_path: str | None = None,
) -> dict:
    work_item_id: str | None = None
    parent_work_item_id: str | None = None

    if transition_decision_artifact is None:
        if work_item is None or post_execution_decision_artifact is None or post_execution_decision_artifact_path is None:
            raise NextStepOrchestrationError("Missing transition decision and insufficient compatibility inputs.")

        transition_decision_artifact, transition_decision_artifact_path, resolved_execution_result_path = (
            _normalize_transition_from_legacy(
                work_item=work_item,
                post_execution_decision_artifact=post_execution_decision_artifact,
                post_execution_decision_artifact_path=post_execution_decision_artifact_path,
            )
        )
        execution_result_artifact_path = execution_result_artifact_path or resolved_execution_result_path
        work_item_id = work_item.get("work_item_id")
        parent_work_item_id = work_item.get("parent_work_item_id")
    else:
        if not transition_decision_artifact_path:
            raise NextStepOrchestrationError("transition_decision_artifact_path is required.")

    try:
        validate_prompt_queue_transition_decision_artifact(transition_decision_artifact)
    except PromptQueueTransitionArtifactValidationError as exc:
        raise NextStepOrchestrationError(f"Malformed transition decision artifact: {exc}") from exc

    action = transition_decision_artifact.get("transition_action")
    if action not in _ACTION_MAP:
        raise NextStepOrchestrationError(f"Unsupported transition action for next-step orchestration: {action}")

    action_status, action_reason_code, decision_status = _ACTION_MAP[action]
    generated_at = iso_now(clock)
    artifact = {
        "next_step_action_artifact_id": f"nextstep-{work_item_id or transition_decision_artifact['step_id']}-{generated_at}",
        "work_item_id": work_item_id or transition_decision_artifact["step_id"],
        "parent_work_item_id": parent_work_item_id,
        "post_execution_decision_artifact_path": transition_decision_artifact_path,
        "execution_result_artifact_path": execution_result_artifact_path
        or transition_decision_artifact.get("source_decision_ref"),
        "action_status": action_status,
        "action_reason_code": action_reason_code,
        "decision_status": decision_status,
        "generated_at": generated_at,
        "generator_version": config.generator_version,
        "spawned_work_item_id": None,
        "blocking_conditions": list(transition_decision_artifact.get("blocking_reasons") or []),
        "warnings": [],
        "source_queue_state_path": source_queue_state_path,
    }
    validate_next_step_action_artifact(artifact)
    return artifact
