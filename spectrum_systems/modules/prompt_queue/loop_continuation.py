"""Deterministic fail-closed continuation from findings reentry to repair child spawn."""

from __future__ import annotations

from typing import Callable

from spectrum_systems.modules.prompt_queue.loop_control_artifact_io import (
    LoopControlArtifactValidationError,
    validate_loop_control_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.queue_artifact_io import (
    ArtifactValidationError,
    validate_findings_reentry,
    validate_repair_prompt_artifact,
    validate_work_item,
)
from spectrum_systems.modules.prompt_queue.queue_models import iso_now, utc_now
from spectrum_systems.modules.prompt_queue.repair_child_queue_integration import (
    RepairChildQueueIntegrationError,
    spawn_repair_child_in_queue,
)

GENERATOR_VERSION = "prompt_queue_loop_continuation.v1"


class LoopContinuationError(ValueError):
    """Raised when loop continuation evaluation cannot proceed safely."""


def _build_artifact_id(work_item_id: str, generated_at: str) -> str:
    stamp = generated_at.replace("-", "").replace(":", "")
    return f"loop-continuation-{work_item_id}-{stamp}"


def _has_duplicate_spawn(queue_state: dict, parent_work_item_id: str, repair_prompt_artifact_path: str) -> bool:
    for item in queue_state.get("work_items", []):
        if item.get("parent_work_item_id") != parent_work_item_id:
            continue
        if item.get("spawned_from_repair_prompt_artifact_path") == repair_prompt_artifact_path:
            return True
    return False


def _validate_lineage(
    *,
    work_item: dict,
    findings_reentry_artifact: dict,
    findings_reentry_artifact_path: str,
    repair_prompt_artifact: dict,
    repair_prompt_artifact_path: str,
    loop_control_decision_artifact: dict | None,
    loop_control_decision_artifact_path: str | None,
) -> None:
    work_item_id = work_item.get("work_item_id")
    parent_work_item_id = work_item.get("parent_work_item_id")

    if findings_reentry_artifact.get("work_item_id") != work_item_id:
        raise LoopContinuationError("Invalid lineage: findings reentry work_item_id mismatch.")
    if findings_reentry_artifact.get("parent_work_item_id") != parent_work_item_id:
        raise LoopContinuationError("Invalid lineage: findings reentry parent_work_item_id mismatch.")
    if findings_reentry_artifact.get("repair_prompt_artifact_path") != repair_prompt_artifact_path:
        raise LoopContinuationError("Invalid lineage: findings reentry repair prompt path mismatch.")

    if repair_prompt_artifact.get("work_item_id") != work_item_id:
        raise LoopContinuationError("Invalid lineage: repair prompt work_item_id mismatch.")

    expected_reentry_path = work_item.get("findings_reentry_artifact_path")
    if expected_reentry_path not in (None, findings_reentry_artifact_path):
        raise LoopContinuationError("Invalid lineage: work item findings_reentry_artifact_path mismatch.")

    expected_repair_path = work_item.get("repair_prompt_artifact_path")
    if expected_repair_path not in (None, repair_prompt_artifact_path):
        raise LoopContinuationError("Invalid lineage: work item repair_prompt_artifact_path mismatch.")

    expected_loop_control_path = work_item.get("loop_control_decision_artifact_path")
    if expected_loop_control_path not in (None, loop_control_decision_artifact_path):
        raise LoopContinuationError("Invalid lineage: work item loop_control_decision_artifact_path mismatch.")

    if loop_control_decision_artifact is not None:
        if loop_control_decision_artifact.get("work_item_id") != work_item_id:
            raise LoopContinuationError("Invalid lineage: loop control work_item_id mismatch.")
        if loop_control_decision_artifact.get("parent_work_item_id") != parent_work_item_id:
            raise LoopContinuationError("Invalid lineage: loop control parent_work_item_id mismatch.")


def _build_outcome(
    *,
    work_item: dict,
    findings_reentry_artifact_path: str,
    repair_prompt_artifact_path: str,
    loop_control_decision_artifact_path: str | None,
    continuation_status: str,
    continuation_reason_code: str,
    generated_at: str,
    source_queue_state_path: str | None,
    spawned_child_work_item_id: str | None = None,
    blocking_conditions: list[str] | None = None,
) -> dict:
    return {
        "loop_continuation_artifact": {
            "loop_continuation_artifact_id": _build_artifact_id(work_item["work_item_id"], generated_at),
            "work_item_id": work_item["work_item_id"],
            "parent_work_item_id": work_item.get("parent_work_item_id"),
            "findings_reentry_artifact_path": findings_reentry_artifact_path,
            "repair_prompt_artifact_path": repair_prompt_artifact_path,
            "loop_control_decision_artifact_path": loop_control_decision_artifact_path,
            "spawned_child_work_item_id": spawned_child_work_item_id,
            "continuation_status": continuation_status,
            "continuation_reason_code": continuation_reason_code,
            "source_queue_state_path": source_queue_state_path,
            "warnings": [],
            "blocking_conditions": blocking_conditions or [],
            "generated_at": generated_at,
            "generator_version": GENERATOR_VERSION,
        },
        "updated_queue_state": None,
        "updated_parent_work_item": None,
        "spawned_child_work_item": None,
    }


def run_loop_continuation(
    *,
    queue_state: dict,
    work_item: dict,
    findings_reentry_artifact: dict,
    findings_reentry_artifact_path: str,
    repair_prompt_artifact: dict,
    repair_prompt_artifact_path: str,
    loop_control_decision_artifact: dict | None,
    loop_control_decision_artifact_path: str | None,
    source_queue_state_path: str | None = None,
    clock: Callable = utc_now,
) -> dict:
    """Evaluate continuation and spawn repair child only when deterministic preconditions pass."""
    try:
        validate_work_item(work_item)
        validate_findings_reentry(findings_reentry_artifact)
        validate_repair_prompt_artifact(repair_prompt_artifact)
    except ArtifactValidationError as exc:
        raise LoopContinuationError(str(exc)) from exc

    if loop_control_decision_artifact is not None:
        try:
            validate_loop_control_decision_artifact(loop_control_decision_artifact)
        except LoopControlArtifactValidationError as exc:
            raise LoopContinuationError(str(exc)) from exc

    if not findings_reentry_artifact_path:
        raise LoopContinuationError("Missing findings reentry artifact path.")
    if not repair_prompt_artifact_path:
        raise LoopContinuationError("Missing repair prompt artifact path.")

    _validate_lineage(
        work_item=work_item,
        findings_reentry_artifact=findings_reentry_artifact,
        findings_reentry_artifact_path=findings_reentry_artifact_path,
        repair_prompt_artifact=repair_prompt_artifact,
        repair_prompt_artifact_path=repair_prompt_artifact_path,
        loop_control_decision_artifact=loop_control_decision_artifact,
        loop_control_decision_artifact_path=loop_control_decision_artifact_path,
    )

    generated_at = iso_now(clock)

    if findings_reentry_artifact.get("reentry_status") != "reentry_completed":
        return _build_outcome(
            work_item=work_item,
            findings_reentry_artifact_path=findings_reentry_artifact_path,
            repair_prompt_artifact_path=repair_prompt_artifact_path,
            loop_control_decision_artifact_path=loop_control_decision_artifact_path,
            continuation_status="continuation_not_needed",
            continuation_reason_code="continuation_not_needed_reentry_not_completed",
            generated_at=generated_at,
            source_queue_state_path=source_queue_state_path,
        )

    if _has_duplicate_spawn(queue_state, work_item["work_item_id"], repair_prompt_artifact_path):
        return _build_outcome(
            work_item=work_item,
            findings_reentry_artifact_path=findings_reentry_artifact_path,
            repair_prompt_artifact_path=repair_prompt_artifact_path,
            loop_control_decision_artifact_path=loop_control_decision_artifact_path,
            continuation_status="continuation_blocked",
            continuation_reason_code="continuation_blocked_duplicate_spawn",
            generated_at=generated_at,
            source_queue_state_path=source_queue_state_path,
            blocking_conditions=["duplicate_repair_prompt_spawn"],
        )

    if loop_control_decision_artifact is not None and loop_control_decision_artifact.get("enforcement_action") != "allow_reentry":
        return _build_outcome(
            work_item=work_item,
            findings_reentry_artifact_path=findings_reentry_artifact_path,
            repair_prompt_artifact_path=repair_prompt_artifact_path,
            loop_control_decision_artifact_path=loop_control_decision_artifact_path,
            continuation_status="continuation_blocked",
            continuation_reason_code="continuation_blocked_loop_control",
            generated_at=generated_at,
            source_queue_state_path=source_queue_state_path,
            blocking_conditions=["loop_control_blocked_reentry"],
        )

    try:
        updated_queue, updated_parent, child = spawn_repair_child_in_queue(
            queue_state=queue_state,
            parent_work_item_id=work_item["work_item_id"],
            repair_prompt_artifact=repair_prompt_artifact,
            repair_prompt_artifact_path=repair_prompt_artifact_path,
            clock=clock,
        )
    except RepairChildQueueIntegrationError:
        return _build_outcome(
            work_item=work_item,
            findings_reentry_artifact_path=findings_reentry_artifact_path,
            repair_prompt_artifact_path=repair_prompt_artifact_path,
            loop_control_decision_artifact_path=loop_control_decision_artifact_path,
            continuation_status="continuation_failed",
            continuation_reason_code="continuation_failed_child_creation",
            generated_at=generated_at,
            source_queue_state_path=source_queue_state_path,
            blocking_conditions=["child_creation_failed"],
        )

    result = _build_outcome(
        work_item=work_item,
        findings_reentry_artifact_path=findings_reentry_artifact_path,
        repair_prompt_artifact_path=repair_prompt_artifact_path,
        loop_control_decision_artifact_path=loop_control_decision_artifact_path,
        continuation_status="child_spawned",
        continuation_reason_code="continuation_child_spawned",
        generated_at=generated_at,
        source_queue_state_path=source_queue_state_path,
        spawned_child_work_item_id=child["work_item_id"],
    )
    result["updated_queue_state"] = updated_queue
    result["updated_parent_work_item"] = updated_parent
    result["spawned_child_work_item"] = child
    return result
