"""Loop-control integration with legacy queue mutation and transition receipt surfaces."""

from __future__ import annotations

from spectrum_systems.modules.prompt_queue.loop_control_artifact_io import (
    LoopControlArtifactValidationError,
    validate_loop_control_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.prompt_queue_transition_artifact_io import (
    PromptQueueTransitionArtifactValidationError,
    validate_prompt_queue_transition_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.queue_artifact_io import (
    ArtifactValidationError,
    validate_queue_state,
    validate_work_item,
)
from spectrum_systems.modules.prompt_queue.queue_models import WorkItemStatus, iso_now, utc_now
from spectrum_systems.modules.prompt_queue.queue_state_machine import IllegalTransitionError, transition_work_item


class LoopControlQueueIntegrationError(ValueError):
    """Raised when loop control queue integration fails closed."""


_ALLOWED_TUPLES = {
    ("within_budget", "allow_reentry", "within_budget_allow_reentry"): WorkItemStatus.REENTRY_ELIGIBLE.value,
    ("limit_reached", "require_review", "limit_reached_require_review"): WorkItemStatus.REVIEW_REQUIRED.value,
    ("limit_exceeded", "block_reentry", "limit_exceeded_block_reentry"): WorkItemStatus.BLOCKED.value,
}


def _find_work_item_index(queue_state: dict, work_item_id: str) -> int:
    for idx, item in enumerate(queue_state.get("work_items", [])):
        if item.get("work_item_id") == work_item_id:
            return idx
    raise LoopControlQueueIntegrationError(f"Work item '{work_item_id}' not found in queue state.")


def _find_work_item(queue_state: dict, work_item_id: str | None) -> dict | None:
    if work_item_id is None:
        return None
    for item in queue_state.get("work_items", []):
        if item.get("work_item_id") == work_item_id:
            return item
    return None


def _resolve_target_status(artifact: dict) -> str:
    key = (
        artifact.get("loop_control_status"),
        artifact.get("enforcement_action"),
        artifact.get("reason_code"),
    )
    if key not in _ALLOWED_TUPLES:
        raise LoopControlQueueIntegrationError("Invalid canonical loop control tuple; refusing queue mutation.")
    return _ALLOWED_TUPLES[key]


def _transition_from_loop_control(loop_control_decision_artifact: dict) -> dict:
    action = loop_control_decision_artifact.get("enforcement_action")
    mapping = {
        "allow_reentry": "retry_allowed",
        "require_review": "reenter_with_findings",
        "block_reentry": "block",
    }
    transition_action = mapping.get(action)
    if not transition_action:
        raise LoopControlQueueIntegrationError("Invalid canonical loop control tuple; refusing queue mutation.")

    return {
        "transition_decision_id": f"compat-loop-{loop_control_decision_artifact.get('loop_control_decision_artifact_id', 'unknown')}",
        "step_id": "step-001",
        "queue_id": None,
        "trace_linkage": loop_control_decision_artifact.get("work_item_id") or "unknown",
        "source_decision_ref": loop_control_decision_artifact.get("loop_control_decision_artifact_id") or "unknown",
        "batch_decision_artifact_ref": loop_control_decision_artifact.get("post_execution_decision_artifact_path")
        or loop_control_decision_artifact.get("loop_control_decision_artifact_id")
        or "unknown",
        "transition_action": transition_action,
        "transition_status": "blocked" if transition_action == "block" else "allowed",
        "reason_codes": ["block_invalid_report_fail_closed"] if transition_action == "block" else ["warn_findings_request_review"],
        "blocking_reasons": ["unsupported_decision"] if transition_action == "block" else [],
        "derived_from_artifacts": [loop_control_decision_artifact.get("loop_control_decision_artifact_id") or "unknown"],
        "timestamp": loop_control_decision_artifact.get("generated_at") or "2026-03-28T00:00:00Z",
    }


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
    if action not in {"reenter_with_findings", "retry_allowed", "block"}:
        raise LoopControlQueueIntegrationError("Transition action is not loop-control eligible.")

    return {
        "integration_type": "loop_control_transition",
        "queue_mutation_performed": False,
        "transition_decision_artifact_path": transition_decision_artifact_path,
        "transition_action": action,
        "transition_status": transition_decision_artifact["transition_status"],
        "blocking_reasons": list(transition_decision_artifact.get("blocking_reasons") or []),
    }


def apply_loop_control_decision_to_queue(
    *,
    queue_state: dict,
    work_item_id: str,
    loop_control_decision_artifact: dict,
    loop_control_decision_artifact_path: str,
    clock=utc_now,
) -> tuple[dict, dict]:
    queue_copy = dict(queue_state)
    queue_copy["work_items"] = [dict(item) for item in queue_state.get("work_items", [])]

    try:
        validate_loop_control_decision_artifact(loop_control_decision_artifact)
    except LoopControlArtifactValidationError as exc:
        raise LoopControlQueueIntegrationError(str(exc)) from exc

    transition = _transition_from_loop_control(loop_control_decision_artifact)
    emit_loop_control_transition_receipt(
        queue_state=queue_copy,
        transition_decision_artifact=transition,
        transition_decision_artifact_path=loop_control_decision_artifact_path,
    )

    idx = _find_work_item_index(queue_copy, work_item_id)
    target = dict(queue_copy["work_items"][idx])

    if loop_control_decision_artifact.get("work_item_id") != work_item_id:
        raise LoopControlQueueIntegrationError("Loop control decision work_item_id does not match target work item.")

    target_generation = target.get("generation_count")
    if target_generation != loop_control_decision_artifact.get("generation_count"):
        raise LoopControlQueueIntegrationError("Loop control generation_count does not match target work item.")

    parent_id = target.get("parent_work_item_id")
    if parent_id != loop_control_decision_artifact.get("parent_work_item_id"):
        raise LoopControlQueueIntegrationError("Loop control parent_work_item_id mismatch with target work item.")

    if target_generation and not _find_work_item(queue_copy, parent_id):
        raise LoopControlQueueIntegrationError("Invalid lineage: parent work item missing from queue state.")

    target_status = _resolve_target_status(loop_control_decision_artifact)

    try:
        target = transition_work_item(target, target_status, clock=clock)
    except IllegalTransitionError as exc:
        raise LoopControlQueueIntegrationError(f"Invalid state transition for loop control decision: {exc}") from exc

    target["loop_control_decision_artifact_path"] = loop_control_decision_artifact_path
    target["updated_at"] = iso_now(clock)

    if target_status == WorkItemStatus.BLOCKED.value and target.get("child_work_item_ids"):
        raise LoopControlQueueIntegrationError("Blocked work items must not spawn further children.")

    queue_copy["work_items"][idx] = target
    queue_copy["updated_at"] = iso_now(clock)

    try:
        validate_work_item(target)
        validate_queue_state(queue_copy)
    except ArtifactValidationError as exc:
        raise LoopControlQueueIntegrationError(str(exc)) from exc

    return queue_copy, target
