"""Pure deterministic blocked-item recovery policy for governed prompt queue items."""

from __future__ import annotations

from dataclasses import dataclass

from spectrum_systems.modules.prompt_queue.queue_artifact_io import ArtifactValidationError, validate_work_item
from spectrum_systems.modules.prompt_queue.queue_models import iso_now, utc_now
from spectrum_systems.modules.prompt_queue.blocked_recovery_artifact_io import validate_blocked_recovery_decision_artifact

_RECOVERABLE_REASON_CODES = {
    "blocked_transient_artifact_write_failure",
    "blocked_transient_artifact_update_failure",
}

_MANUAL_REVIEW_REASON_CODES = {
    "blocked_lineage_mismatch",
    "blocked_duplicate_protection_conflict",
    "blocked_partial_provider_result",
}

_NON_RECOVERABLE_REASON_CODES = {
    "blocked_missing_critical_lineage",
    "blocked_state_corruption",
    "blocked_unsupported_reason",
}


@dataclass(frozen=True)
class BlockedRecoveryPolicyConfig:
    generator_version: str = "prompt_queue_blocked_recovery_policy.v1"


class BlockedRecoveryPolicyError(ValueError):
    """Raised when blocked recovery policy inputs are invalid."""


def evaluate_blocked_recovery_policy(
    *,
    work_item: dict,
    blocking_reason_code: str,
    source_blocking_artifact_path: str | None,
    prior_state: str | None,
    source_queue_state_path: str | None,
    config: BlockedRecoveryPolicyConfig = BlockedRecoveryPolicyConfig(),
    clock=utc_now,
) -> dict:
    """Classify blocked work item into a deterministic recovery decision artifact."""
    try:
        validate_work_item(work_item)
    except ArtifactValidationError as exc:
        raise BlockedRecoveryPolicyError(str(exc)) from exc

    if work_item.get("status") != "blocked":
        raise BlockedRecoveryPolicyError("Blocked recovery policy requires work item status='blocked'.")

    blocking_conditions: list[str] = []
    warnings: list[str] = []
    required_manual_inputs: list[str] = []

    if source_blocking_artifact_path is None:
        warnings.append("source_blocking_artifact_path_missing")

    if blocking_reason_code in _RECOVERABLE_REASON_CODES:
        recovery_status = "recoverable"
        recovery_action = "return_to_prior_state"
        recovery_reason_code = "recoverable_transient_artifact_failure_return_to_prior_state"
        if not prior_state:
            recovery_status = "non_recoverable"
            recovery_action = "no_action"
            recovery_reason_code = "non_recoverable_missing_critical_lineage"
            blocking_conditions.append("missing_prior_state_for_recovery")
    elif blocking_reason_code in _MANUAL_REVIEW_REASON_CODES:
        recovery_status = "manual_review_required"
        recovery_action = "no_action"
        recovery_reason_map = {
            "blocked_lineage_mismatch": "manual_review_required_lineage_mismatch",
            "blocked_duplicate_protection_conflict": "manual_review_required_duplicate_conflict",
            "blocked_partial_provider_result": "manual_review_required_partial_provider_result",
        }
        recovery_reason_code = recovery_reason_map[blocking_reason_code]
        required_manual_inputs.append("operator_recovery_approval")
    elif blocking_reason_code in _NON_RECOVERABLE_REASON_CODES:
        recovery_status = "non_recoverable"
        recovery_action = "no_action"
        recovery_reason_map = {
            "blocked_missing_critical_lineage": "non_recoverable_missing_critical_lineage",
            "blocked_state_corruption": "non_recoverable_state_corruption",
            "blocked_unsupported_reason": "non_recoverable_unsupported_blocked_reason",
        }
        recovery_reason_code = recovery_reason_map[blocking_reason_code]
    else:
        recovery_status = "non_recoverable"
        recovery_action = "no_action"
        recovery_reason_code = "non_recoverable_unsupported_blocked_reason"
        blocking_conditions.append("unsupported_blocking_reason")

    generated_at = iso_now(clock)
    artifact = {
        "blocked_recovery_decision_artifact_id": f"blocked-recovery-{work_item['work_item_id']}-{generated_at}",
        "work_item_id": work_item["work_item_id"],
        "parent_work_item_id": work_item.get("parent_work_item_id"),
        "blocking_state": "blocked",
        "blocking_reason_code": blocking_reason_code,
        "source_blocking_artifact_path": source_blocking_artifact_path,
        "recovery_status": recovery_status,
        "recovery_action": recovery_action,
        "recovery_reason_code": recovery_reason_code,
        "source_queue_state_path": source_queue_state_path,
        "prior_state": prior_state,
        "warnings": warnings,
        "blocking_conditions": blocking_conditions,
        "required_manual_inputs": required_manual_inputs,
        "generated_at": generated_at,
        "generator_version": config.generator_version,
    }
    validate_blocked_recovery_decision_artifact(artifact)
    return artifact
