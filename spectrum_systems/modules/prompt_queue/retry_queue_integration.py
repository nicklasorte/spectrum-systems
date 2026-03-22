"""Pure queue integration for deterministic prompt queue retry decisions."""

from __future__ import annotations

from spectrum_systems.modules.prompt_queue.queue_artifact_io import (
    ArtifactValidationError,
    validate_queue_state,
    validate_work_item,
)
from spectrum_systems.modules.prompt_queue.queue_models import iso_now, utc_now
from spectrum_systems.modules.prompt_queue.retry_artifact_io import (
    RetryArtifactValidationError,
    validate_retry_decision_artifact,
)


class RetryQueueIntegrationError(ValueError):
    """Raised when retry queue integration fails closed."""


_RETRY_STATUS_TO_TARGET_STATE = {
    "executed_failure": "runnable",
    "review_provider_failed": "review_triggered",
    "review_invocation_failed": "review_triggered",
}


def _find_work_item_index(queue_state: dict, work_item_id: str) -> int:
    for idx, item in enumerate(queue_state.get("work_items", [])):
        if item.get("work_item_id") == work_item_id:
            return idx
    raise RetryQueueIntegrationError(f"Work item '{work_item_id}' not found in queue state.")


def apply_retry_decision_to_queue(
    *,
    queue_state: dict,
    work_item_id: str,
    retry_decision_artifact: dict,
    retry_decision_artifact_path: str,
    clock=utc_now,
) -> tuple[dict, dict]:
    queue_copy = dict(queue_state)
    queue_copy["work_items"] = [dict(item) for item in queue_state.get("work_items", [])]

    try:
        validate_retry_decision_artifact(retry_decision_artifact)
    except RetryArtifactValidationError as exc:
        raise RetryQueueIntegrationError(str(exc)) from exc

    idx = _find_work_item_index(queue_copy, work_item_id)
    target = dict(queue_copy["work_items"][idx])

    if target.get("work_item_id") != retry_decision_artifact.get("work_item_id"):
        raise RetryQueueIntegrationError("Retry decision work_item_id does not match target work item.")
    if target.get("parent_work_item_id") != retry_decision_artifact.get("parent_work_item_id"):
        raise RetryQueueIntegrationError("Retry decision parent_work_item_id does not match target work item lineage.")
    if target.get("status") != retry_decision_artifact.get("current_status"):
        raise RetryQueueIntegrationError("Retry decision current_status does not match target work item status.")

    retry_status = retry_decision_artifact["retry_status"]
    retry_action = retry_decision_artifact["retry_action"]

    if retry_decision_artifact["retry_count"] != target.get("retry_count"):
        raise RetryQueueIntegrationError("Retry decision retry_count does not match target work item retry_count.")
    if retry_decision_artifact["retry_budget"] != target.get("retry_budget"):
        raise RetryQueueIntegrationError("Retry decision retry_budget does not match target work item retry_budget.")

    if target.get("status") == "blocked":
        raise RetryQueueIntegrationError("Retry integration forbids blocked work items.")

    if retry_status == "retry_allowed":
        if retry_action != "retry":
            raise RetryQueueIntegrationError("retry_allowed decisions must use retry action.")
        if target["retry_count"] >= target["retry_budget"]:
            raise RetryQueueIntegrationError("Retry budget exhausted; retry initiation blocked.")
        next_state = _RETRY_STATUS_TO_TARGET_STATE.get(target["status"])
        if next_state is None:
            raise RetryQueueIntegrationError(f"Unsupported failure state for retry initiation: {target['status']}")
        target["status"] = next_state
        target["retry_count"] = target["retry_count"] + 1
    elif retry_status in {"retry_exhausted", "retry_blocked"}:
        if retry_action != "no_action":
            raise RetryQueueIntegrationError("retry_blocked/retry_exhausted decisions must use no_action.")
    else:
        raise RetryQueueIntegrationError(f"Unsupported retry status: {retry_status}")

    now = iso_now(clock)
    target["retry_decision_artifact_path"] = retry_decision_artifact_path
    target["updated_at"] = now

    queue_copy["work_items"][idx] = target
    queue_copy["updated_at"] = now

    try:
        validate_work_item(target)
        validate_queue_state(queue_copy)
    except ArtifactValidationError as exc:
        raise RetryQueueIntegrationError(str(exc)) from exc

    return queue_copy, target
