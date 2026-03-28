"""Pure deterministic mapping from unified transition decisions to next-step queue actions."""

from __future__ import annotations

from dataclasses import dataclass

from spectrum_systems.modules.prompt_queue.next_step_action_artifact_io import validate_next_step_action_artifact
from spectrum_systems.modules.prompt_queue.prompt_queue_transition_artifact_io import (
    PromptQueueTransitionArtifactValidationError,
    validate_prompt_queue_transition_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.queue_models import iso_now, utc_now


class NextStepOrchestrationError(ValueError):
    """Raised when next-step orchestration cannot proceed safely."""


@dataclass(frozen=True)
class NextStepOrchestrationConfig:
    generator_version: str = "prompt_queue_next_step_orchestrator.v2"


_ACTION_MAP = {
    "continue": ("marked_complete", "marked_complete_from_post_execution_complete"),
    "request_review": ("spawn_review", "spawn_review_from_post_execution_review_required"),
    "reenter_with_findings": ("spawn_reentry_child", "spawn_reentry_child_from_post_execution_reentry_eligible"),
    "retry_allowed": ("spawn_reentry_child", "spawn_reentry_child_from_post_execution_reentry_eligible"),
    "block": ("blocked_no_action", "blocked_no_action_from_post_execution_reentry_blocked"),
}


def determine_next_step_action(
    *,
    transition_decision_artifact: dict,
    transition_decision_artifact_path: str,
    source_queue_state_path: str | None,
    config: NextStepOrchestrationConfig = NextStepOrchestrationConfig(),
    clock=utc_now,
) -> dict:
    try:
        validate_prompt_queue_transition_decision_artifact(transition_decision_artifact)
    except PromptQueueTransitionArtifactValidationError as exc:
        raise NextStepOrchestrationError(f"Malformed transition decision artifact: {exc}") from exc

    action = transition_decision_artifact.get("transition_action")
    if action not in _ACTION_MAP:
        raise NextStepOrchestrationError(f"Unsupported transition action for next-step orchestration: {action}")

    action_status, action_reason_code = _ACTION_MAP[action]
    generated_at = iso_now(clock)
    artifact = {
        "next_step_action_artifact_id": f"nextstep-{transition_decision_artifact['step_id']}-{generated_at}",
        "work_item_id": transition_decision_artifact["step_id"],
        "parent_work_item_id": None,
        "post_execution_decision_artifact_path": transition_decision_artifact_path,
        "execution_result_artifact_path": transition_decision_artifact.get("source_decision_ref"),
        "action_status": action_status,
        "action_reason_code": action_reason_code,
        "decision_status": {
            "continue": "complete",
            "request_review": "review_required",
            "reenter_with_findings": "reentry_eligible",
            "retry_allowed": "reentry_eligible",
            "block": "reentry_blocked",
        }[action],
        "generated_at": generated_at,
        "generator_version": config.generator_version,
        "spawned_work_item_id": None,
        "blocking_conditions": list(transition_decision_artifact.get("blocking_reasons") or []),
        "warnings": [],
        "source_queue_state_path": source_queue_state_path,
    }
    validate_next_step_action_artifact(artifact)
    return artifact
