"""Deterministic next-step integration with legacy mutation and transition receipt surfaces."""

from __future__ import annotations

from spectrum_systems.modules.prompt_queue.next_step_action_artifact_io import (
    NextStepActionArtifactValidationError,
    validate_next_step_action_artifact,
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
from spectrum_systems.modules.prompt_queue.queue_models import WorkItemStatus, iso_now, make_work_item, utc_now
from spectrum_systems.modules.prompt_queue.queue_state_machine import IllegalTransitionError, transition_work_item


class NextStepQueueIntegrationError(ValueError):
    """Raised when next-step queue integration fails closed."""


def _find_work_item_index(queue_state: dict, work_item_id: str) -> int:
    for idx, item in enumerate(queue_state.get("work_items", [])):
        if item.get("work_item_id") == work_item_id:
            return idx
    raise NextStepQueueIntegrationError(f"Work item '{work_item_id}' not found in queue state.")


def _decision_to_target_status(decision_status: str) -> str:
    mapping = {
        "complete": WorkItemStatus.COMPLETE.value,
        "review_required": WorkItemStatus.REVIEW_REQUIRED.value,
        "reentry_eligible": WorkItemStatus.REENTRY_ELIGIBLE.value,
        "reentry_blocked": WorkItemStatus.REENTRY_BLOCKED.value,
    }
    if decision_status not in mapping:
        raise NextStepQueueIntegrationError(f"Unsupported decision_status for queue integration: {decision_status}")
    return mapping[decision_status]


def _build_spawned_work_item(parent: dict, spawn_kind: str, clock=utc_now) -> dict:
    existing_child_ids = set(parent.get("child_work_item_ids") or [])
    if spawn_kind == "spawn_review":
        suffix = ".review.1"
        prompt_suffix = ":review:1"
        title_suffix = " [review 1]"
    elif spawn_kind == "spawn_reentry_child":
        suffix = ".reentry.1"
        prompt_suffix = ":reentry:1"
        title_suffix = " [reentry 1]"
    else:
        raise NextStepQueueIntegrationError(f"Unsupported spawn action: {spawn_kind}")

    child_id = f"{parent['work_item_id']}{suffix}"
    if child_id in existing_child_ids:
        raise NextStepQueueIntegrationError(f"Duplicate spawn detected: child '{child_id}' already linked to parent.")

    child = make_work_item(
        work_item_id=child_id,
        prompt_id=f"{parent['prompt_id']}{prompt_suffix}",
        title=f"{parent['title']}{title_suffix}",
        priority=parent["priority"],
        risk_level=parent["risk_level"],
        repo=parent["repo"],
        branch=parent["branch"],
        scope_paths=parent["scope_paths"],
        parent_work_item_id=parent["work_item_id"],
        clock=clock,
    )

    child["spawned_from_repair_prompt_artifact_path"] = parent.get("repair_prompt_artifact_path")
    child["spawned_from_findings_artifact_path"] = parent.get("spawned_from_findings_artifact_path")
    child["spawned_from_review_artifact_path"] = parent.get("spawned_from_review_artifact_path")
    child["gating_decision_artifact_path"] = parent.get("gating_decision_artifact_path")
    child["execution_result_artifact_path"] = parent.get("execution_result_artifact_path")
    child["post_execution_decision_artifact_path"] = parent.get("post_execution_decision_artifact_path")
    child["repair_loop_generation"] = int(parent.get("repair_loop_generation") or 0) + 1
    child["next_step_action_artifact_path"] = None
    return child


def _detect_duplicate_spawn(queue_state: dict, parent_work_item_id: str, action_path: str) -> None:
    for item in queue_state.get("work_items", []):
        if item.get("parent_work_item_id") != parent_work_item_id:
            continue
        if item.get("next_step_action_artifact_path") == action_path:
            raise NextStepQueueIntegrationError(
                "Duplicate spawn detected: next-step action artifact already consumed by existing child."
            )


def _transition_from_next_step_action(next_step_action_artifact: dict) -> dict:
    action = next_step_action_artifact.get("action_status")
    mapping = {
        "marked_complete": "continue",
        "spawn_review": "request_review",
        "spawn_reentry_child": "reenter_with_findings",
        "blocked_no_action": "block",
    }
    transition_action = mapping.get(action)
    if not transition_action:
        raise NextStepQueueIntegrationError("Invalid next-step action for transition compatibility mapping.")
    return {
        "transition_decision_id": f"compat-next-step-{next_step_action_artifact.get('next_step_action_artifact_id', 'unknown')}",
        "step_id": "step-001",
        "queue_id": None,
        "trace_linkage": next_step_action_artifact.get("work_item_id") or "unknown",
        "source_decision_ref": next_step_action_artifact.get("execution_result_artifact_path")
        or next_step_action_artifact.get("post_execution_decision_artifact_path")
        or "unknown",
        "transition_action": transition_action,
        "transition_status": "blocked" if transition_action == "block" else "allowed",
        "reason_codes": ["block_invalid_report_fail_closed"] if transition_action == "block" else ["warn_findings_request_review"],
        "blocking_reasons": ["unsupported_decision"] if transition_action == "block" else [],
        "derived_from_artifacts": [
            next_step_action_artifact.get("execution_result_artifact_path")
            or next_step_action_artifact.get("post_execution_decision_artifact_path")
            or "unknown"
        ],
        "timestamp": next_step_action_artifact.get("generated_at") or "2026-03-28T00:00:00Z",
    }


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


def apply_next_step_action_to_queue(
    *,
    queue_state: dict,
    work_item_id: str,
    next_step_action_artifact: dict,
    next_step_action_artifact_path: str,
    clock=utc_now,
) -> tuple[dict, dict, dict | None, dict]:
    queue_copy = dict(queue_state)
    queue_copy["work_items"] = [dict(item) for item in queue_state.get("work_items", [])]

    try:
        validate_next_step_action_artifact(next_step_action_artifact)
    except NextStepActionArtifactValidationError as exc:
        raise NextStepQueueIntegrationError(str(exc)) from exc

    transition = _transition_from_next_step_action(next_step_action_artifact)
    emit_next_step_transition_receipt(
        queue_state=queue_copy,
        transition_decision_artifact=transition,
        transition_decision_artifact_path=next_step_action_artifact_path,
    )

    idx = _find_work_item_index(queue_copy, work_item_id)
    target = dict(queue_copy["work_items"][idx])

    if next_step_action_artifact.get("work_item_id") != work_item_id:
        raise NextStepQueueIntegrationError("next-step action work_item_id does not match target work item.")

    if next_step_action_artifact.get("parent_work_item_id") != target.get("parent_work_item_id"):
        raise NextStepQueueIntegrationError("next-step action parent_work_item_id mismatch.")

    if next_step_action_artifact.get("post_execution_decision_artifact_path") != target.get(
        "post_execution_decision_artifact_path"
    ):
        raise NextStepQueueIntegrationError("next-step action post_execution_decision_artifact_path mismatch.")

    if next_step_action_artifact.get("execution_result_artifact_path") != target.get("execution_result_artifact_path"):
        raise NextStepQueueIntegrationError("next-step action execution_result_artifact_path mismatch.")

    target_status = _decision_to_target_status(next_step_action_artifact["decision_status"])
    try:
        target = transition_work_item(target, target_status, clock=clock)
    except IllegalTransitionError as exc:
        raise NextStepQueueIntegrationError(str(exc)) from exc

    target.setdefault("child_work_item_ids", [])
    target["next_step_action_artifact_path"] = next_step_action_artifact_path
    target["updated_at"] = iso_now(clock)

    spawned_child = None
    action_status = next_step_action_artifact.get("action_status")
    if action_status in {"spawn_review", "spawn_reentry_child"}:
        _detect_duplicate_spawn(queue_copy, work_item_id, next_step_action_artifact_path)
        spawned_child = _build_spawned_work_item(target, action_status, clock=clock)
        for existing in queue_copy["work_items"]:
            if existing.get("work_item_id") == spawned_child["work_item_id"]:
                raise NextStepQueueIntegrationError(
                    f"Duplicate spawn detected: child work item '{spawned_child['work_item_id']}' already exists."
                )
        spawned_child["next_step_action_artifact_path"] = next_step_action_artifact_path
        target["child_work_item_ids"] = [*target["child_work_item_ids"], spawned_child["work_item_id"]]

    queue_copy["work_items"][idx] = target
    if spawned_child is not None:
        queue_copy["work_items"].append(spawned_child)
    queue_copy["updated_at"] = iso_now(clock)

    updated_action = dict(next_step_action_artifact)
    updated_action["spawned_work_item_id"] = spawned_child.get("work_item_id") if spawned_child else None

    try:
        validate_work_item(target)
        if spawned_child is not None:
            validate_work_item(spawned_child)
        validate_queue_state(queue_copy)
        validate_next_step_action_artifact(updated_action)
    except (ArtifactValidationError, NextStepActionArtifactValidationError) as exc:
        raise NextStepQueueIntegrationError(str(exc)) from exc

    return queue_copy, target, spawned_child, updated_action
