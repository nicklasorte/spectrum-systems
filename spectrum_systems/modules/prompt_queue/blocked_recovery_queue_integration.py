"""Pure queue integration for deterministic blocked-item recovery decisions."""

from __future__ import annotations

from spectrum_systems.modules.prompt_queue.blocked_recovery_artifact_io import (
    BlockedRecoveryArtifactValidationError,
    validate_blocked_recovery_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.queue_artifact_io import (
    ArtifactValidationError,
    validate_queue_state,
    validate_work_item,
)
from spectrum_systems.modules.prompt_queue.queue_models import iso_now, utc_now


class BlockedRecoveryQueueIntegrationError(ValueError):
    """Raised when blocked recovery queue integration fails closed."""


_ALLOWED_RECOVERY_PRIOR_STATES = {
    "queued",
    "review_queued",
    "review_triggered",
    "execution_gated",
    "approval_required",
    "runnable",
}


def _find_work_item_index(queue_state: dict, work_item_id: str) -> int:
    for idx, item in enumerate(queue_state.get("work_items", [])):
        if item.get("work_item_id") == work_item_id:
            return idx
    raise BlockedRecoveryQueueIntegrationError(f"Work item '{work_item_id}' not found in queue state.")


def apply_blocked_recovery_decision_to_queue(
    *,
    queue_state: dict,
    work_item_id: str,
    blocked_recovery_decision_artifact: dict,
    blocked_recovery_decision_artifact_path: str,
    clock=utc_now,
) -> tuple[dict, dict]:
    queue_copy = dict(queue_state)
    queue_copy["work_items"] = [dict(item) for item in queue_state.get("work_items", [])]

    try:
        validate_blocked_recovery_decision_artifact(blocked_recovery_decision_artifact)
    except BlockedRecoveryArtifactValidationError as exc:
        raise BlockedRecoveryQueueIntegrationError(str(exc)) from exc

    idx = _find_work_item_index(queue_copy, work_item_id)
    target = dict(queue_copy["work_items"][idx])

    if target.get("work_item_id") != blocked_recovery_decision_artifact.get("work_item_id"):
        raise BlockedRecoveryQueueIntegrationError("Recovery decision work_item_id does not match target work item.")
    if target.get("status") != "blocked":
        raise BlockedRecoveryQueueIntegrationError("Recovery integration requires target work item in blocked status.")
    if target.get("blocked_recovery_decision_artifact_path"):
        raise BlockedRecoveryQueueIntegrationError("Recovery decision already attached for this work item; duplicate attempt blocked.")

    if blocked_recovery_decision_artifact.get("blocking_state") != "blocked":
        raise BlockedRecoveryQueueIntegrationError("Unsupported blocking_state in recovery decision artifact.")

    recovery_status = blocked_recovery_decision_artifact["recovery_status"]
    recovery_action = blocked_recovery_decision_artifact["recovery_action"]

    if recovery_status == "recoverable":
        if recovery_action != "return_to_prior_state":
            raise BlockedRecoveryQueueIntegrationError("Unsupported recovery action for recoverable status.")
        prior_state = blocked_recovery_decision_artifact.get("prior_state")
        if not prior_state:
            raise BlockedRecoveryQueueIntegrationError("Missing required prior_state for recoverable decision.")
        if prior_state not in _ALLOWED_RECOVERY_PRIOR_STATES:
            raise BlockedRecoveryQueueIntegrationError(f"Unsupported prior_state for bounded recovery action: {prior_state}")
        if not blocked_recovery_decision_artifact.get("source_blocking_artifact_path"):
            raise BlockedRecoveryQueueIntegrationError("Missing required source blocking artifact evidence for recoverable decision.")
        target["status"] = prior_state
    elif recovery_status in {"manual_review_required", "non_recoverable"}:
        if recovery_action != "no_action":
            raise BlockedRecoveryQueueIntegrationError("manual_review_required/non_recoverable decisions must use no_action.")
    else:
        raise BlockedRecoveryQueueIntegrationError(f"Unsupported recovery status: {recovery_status}")

    now = iso_now(clock)
    target["blocked_recovery_decision_artifact_path"] = blocked_recovery_decision_artifact_path
    target["updated_at"] = now

    queue_copy["work_items"][idx] = target
    queue_copy["updated_at"] = now

    try:
        validate_work_item(target)
        validate_queue_state(queue_copy)
    except ArtifactValidationError as exc:
        raise BlockedRecoveryQueueIntegrationError(str(exc)) from exc

    return queue_copy, target
