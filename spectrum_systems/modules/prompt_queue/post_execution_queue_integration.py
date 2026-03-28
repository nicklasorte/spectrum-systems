"""Read-only integration for post-execution transition decisions (no queue mutation)."""

from __future__ import annotations

from spectrum_systems.modules.prompt_queue.prompt_queue_transition_artifact_io import (
    PromptQueueTransitionArtifactValidationError,
    validate_prompt_queue_transition_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.queue_artifact_io import ArtifactValidationError, validate_queue_state


class PostExecutionQueueIntegrationError(ValueError):
    """Raised when post-execution transition integration fails closed."""


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
