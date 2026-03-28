"""Read-only loop-control integration for unified transition decisions."""

from __future__ import annotations

from spectrum_systems.modules.prompt_queue.prompt_queue_transition_artifact_io import (
    PromptQueueTransitionArtifactValidationError,
    validate_prompt_queue_transition_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.queue_artifact_io import ArtifactValidationError, validate_queue_state


class LoopControlQueueIntegrationError(ValueError):
    """Raised when loop control queue integration fails closed."""


_ALLOWED_LOOP_TRANSITIONS = {"reenter_with_findings", "retry_allowed", "block"}


def emit_loop_control_transition_receipt(
    *,
    queue_state: dict,
    transition_decision_artifact: dict,
    transition_decision_artifact_path: str,
) -> dict:
    try:
        validate_queue_state(queue_state)
    except ArtifactValidationError as exc:
        raise LoopControlQueueIntegrationError(str(exc)) from exc

    try:
        validate_prompt_queue_transition_decision_artifact(transition_decision_artifact)
    except PromptQueueTransitionArtifactValidationError as exc:
        raise LoopControlQueueIntegrationError(str(exc)) from exc

    action = transition_decision_artifact["transition_action"]
    if action not in _ALLOWED_LOOP_TRANSITIONS:
        raise LoopControlQueueIntegrationError("Transition action is not loop-control eligible.")

    return {
        "integration_type": "loop_control_transition",
        "queue_mutation_performed": False,
        "transition_decision_artifact_path": transition_decision_artifact_path,
        "transition_action": action,
        "transition_status": transition_decision_artifact["transition_status"],
        "blocking_reasons": list(transition_decision_artifact.get("blocking_reasons") or []),
    }
