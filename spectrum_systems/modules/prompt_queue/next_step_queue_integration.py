"""Read-only next-step integration driven by unified transition decisions."""

from __future__ import annotations

from spectrum_systems.modules.prompt_queue.prompt_queue_transition_artifact_io import (
    PromptQueueTransitionArtifactValidationError,
    validate_prompt_queue_transition_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.queue_artifact_io import ArtifactValidationError, validate_queue_state


class NextStepQueueIntegrationError(ValueError):
    """Raised when next-step queue integration fails closed."""


def emit_next_step_transition_receipt(
    *,
    queue_state: dict,
    transition_decision_artifact: dict,
    transition_decision_artifact_path: str,
) -> dict:
    try:
        validate_queue_state(queue_state)
    except ArtifactValidationError as exc:
        raise NextStepQueueIntegrationError(str(exc)) from exc

    try:
        validate_prompt_queue_transition_decision_artifact(transition_decision_artifact)
    except PromptQueueTransitionArtifactValidationError as exc:
        raise NextStepQueueIntegrationError(str(exc)) from exc

    if transition_decision_artifact["transition_action"] == "block" and transition_decision_artifact["transition_status"] != "blocked":
        raise NextStepQueueIntegrationError("Ambiguous transition status for block action.")

    return {
        "integration_type": "next_step_transition",
        "queue_mutation_performed": False,
        "transition_decision_artifact_path": transition_decision_artifact_path,
        "transition_action": transition_decision_artifact["transition_action"],
        "transition_status": transition_decision_artifact["transition_status"],
        "reason_codes": list(transition_decision_artifact.get("reason_codes") or []),
    }
