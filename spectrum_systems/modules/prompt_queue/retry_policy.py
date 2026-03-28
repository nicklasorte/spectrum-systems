"""Pure deterministic retry policy for governed prompt queue work items."""

from __future__ import annotations

from dataclasses import dataclass

from spectrum_systems.modules.prompt_queue.queue_artifact_io import ArtifactValidationError, validate_work_item
from spectrum_systems.modules.prompt_queue.prompt_queue_transition_artifact_io import (
    PromptQueueTransitionArtifactValidationError,
    validate_prompt_queue_transition_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.queue_models import iso_now, utc_now
from spectrum_systems.modules.prompt_queue.retry_artifact_io import validate_retry_decision_artifact

_RETRYABLE_FAILURE_REASON_CODES = {
    "execution_failure_non_lineage_non_schema",
    "provider_transient_failure",
    "timeout",
}

_NON_RETRYABLE_FAILURE_REASON_CODES = {
    "lineage_mismatch",
    "schema_validation_failure",
    "loop_control_termination",
}

_ELIGIBLE_FAILURE_STATES = {
    "executed_failure",
    "review_provider_failed",
    "review_invocation_failed",
}

_RETRY_ELIGIBLE_TRANSITION_ACTIONS = {"retry_allowed"}


def _is_transition_retry_eligible(transition_decision_artifact: dict | None) -> bool:
    if transition_decision_artifact is None:
        return False
    action = transition_decision_artifact.get("transition_action")
    status = transition_decision_artifact.get("transition_status")
    return action in _RETRY_ELIGIBLE_TRANSITION_ACTIONS and status == "allowed"


@dataclass(frozen=True)
class RetryPolicyConfig:
    generator_version: str = "prompt_queue_retry_policy.v1"


class RetryPolicyError(ValueError):
    """Raised when retry policy inputs are invalid."""


def evaluate_retry_policy(
    *,
    work_item: dict,
    failure_reason_code: str,
    source_queue_state_path: str | None,
    transition_decision_artifact: dict | None = None,
    config: RetryPolicyConfig = RetryPolicyConfig(),
    clock=utc_now,
) -> dict:
    """Evaluate retry eligibility in a deterministic fail-closed manner."""
    try:
        validate_work_item(work_item)
    except ArtifactValidationError as exc:
        raise RetryPolicyError(str(exc)) from exc

    if transition_decision_artifact is not None:
        try:
            validate_prompt_queue_transition_decision_artifact(transition_decision_artifact)
        except PromptQueueTransitionArtifactValidationError as exc:
            raise RetryPolicyError(f"Malformed transition decision artifact: {exc}") from exc

        if transition_decision_artifact.get("source_decision_ref") != work_item.get("execution_result_artifact_path"):
            raise RetryPolicyError(
                "Retry decision requires transition decision source_decision_ref to match work_item execution lineage."
            )

    current_status = work_item.get("status")
    retry_count = work_item.get("retry_count")
    retry_budget = work_item.get("retry_budget")

    if not isinstance(retry_count, int) or retry_count < 0:
        raise RetryPolicyError("retry_count must be a non-negative integer.")
    if not isinstance(retry_budget, int) or retry_budget < 0:
        raise RetryPolicyError("retry_budget must be a non-negative integer.")

    warnings: list[str] = []

    if source_queue_state_path is None:
        warnings.append("source_queue_state_path_missing")

    if current_status == "blocked":
        retry_status = "retry_blocked"
        retry_action = "no_action"
        retry_reason_code = "retry_blocked_work_item_blocked"
    elif current_status not in _ELIGIBLE_FAILURE_STATES:
        retry_status = "retry_blocked"
        retry_action = "no_action"
        retry_reason_code = "retry_blocked_invalid_status"
    elif failure_reason_code in _NON_RETRYABLE_FAILURE_REASON_CODES:
        retry_status = "retry_blocked"
        retry_action = "no_action"
        retry_reason_code = "retry_blocked_non_retryable_failure"
    elif failure_reason_code not in _RETRYABLE_FAILURE_REASON_CODES:
        retry_status = "retry_blocked"
        retry_action = "no_action"
        retry_reason_code = "retry_blocked_unsupported_failure_reason"
    elif retry_count >= retry_budget:
        retry_status = "retry_exhausted"
        retry_action = "no_action"
        retry_reason_code = "retry_exhausted_budget_reached"
    elif not _is_transition_retry_eligible(transition_decision_artifact):
        retry_status = "retry_blocked"
        retry_action = "no_action"
        retry_reason_code = "retry_blocked_transition_ineligible"
    else:
        retry_status = "retry_allowed"
        retry_action = "retry"
        retry_reason_code = "retry_allowed_under_budget_retryable_failure"

    generated_at = iso_now(clock)
    artifact = {
        "retry_decision_artifact_id": f"retry-{work_item['work_item_id']}-{generated_at}",
        "work_item_id": work_item["work_item_id"],
        "parent_work_item_id": work_item.get("parent_work_item_id"),
        "current_status": current_status,
        "failure_reason_code": failure_reason_code,
        "retry_status": retry_status,
        "retry_action": retry_action,
        "retry_count": retry_count,
        "retry_budget": retry_budget,
        "retry_reason_code": retry_reason_code,
        "source_queue_state_path": source_queue_state_path,
        "warnings": warnings,
        "generated_at": generated_at,
        "generator_version": config.generator_version,
    }
    validate_retry_decision_artifact(artifact)
    return artifact
