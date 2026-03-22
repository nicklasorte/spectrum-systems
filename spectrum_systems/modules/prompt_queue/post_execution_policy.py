"""Pure deterministic post-execution review/re-entry policy for governed prompt queue."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from spectrum_systems.modules.prompt_queue.execution_artifact_io import (
    ExecutionResultArtifactValidationError,
    validate_execution_result_artifact,
)
from spectrum_systems.modules.prompt_queue.execution_gating_artifact_io import (
    ExecutionGatingArtifactValidationError,
    validate_execution_gating_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.post_execution_artifact_io import (
    validate_post_execution_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.queue_artifact_io import ArtifactValidationError, validate_work_item
from spectrum_systems.modules.prompt_queue.queue_models import WorkItemStatus, iso_now, utc_now


@dataclass(frozen=True)
class PostExecutionPolicyConfig:
    max_generation_allowed: int = 2
    policy_id: str = "prompt_queue_post_execution_policy.v1"
    generator_version: str = "prompt_queue_post_execution_policy.v1"


def evaluate_post_execution_policy(
    *,
    work_item: dict,
    execution_result_artifact: dict,
    execution_result_artifact_path: str,
    gating_decision_artifact: dict,
    gating_decision_artifact_path: str,
    source_queue_state_path: str | None,
    policy: PostExecutionPolicyConfig = PostExecutionPolicyConfig(),
    clock=utc_now,
) -> dict:
    blocking_conditions: list[str] = []
    warnings: list[str] = []

    decision_status = "reentry_blocked"
    reason_code = "reentry_blocked_invalid_artifact"
    execution_status = str(execution_result_artifact.get("execution_status") or "failure")

    approval_required = bool(gating_decision_artifact.get("approval_required", False))
    approval_present = bool(gating_decision_artifact.get("approval_present", False))

    try:
        validate_work_item(work_item)
    except ArtifactValidationError:
        blocking_conditions.append("work_item failed schema validation")
        return _decision_artifact(
            work_item=work_item,
            execution_result_artifact_path=execution_result_artifact_path,
            gating_decision_artifact_path=gating_decision_artifact_path,
            decision_status=decision_status,
            reason_code=reason_code,
            execution_status=execution_status,
            max_generation_allowed=policy.max_generation_allowed,
            approval_required=approval_required,
            approval_present=approval_present,
            policy=policy,
            source_queue_state_path=source_queue_state_path,
            blocking_conditions=blocking_conditions,
            warnings=warnings,
            review_trigger_recommended=False,
            clock=clock,
        )

    if work_item.get("status") not in {
        WorkItemStatus.EXECUTED_SUCCESS.value,
        WorkItemStatus.EXECUTED_FAILURE.value,
    }:
        reason_code = "reentry_blocked_ineligible_status"
        blocking_conditions.append("work_item is not in an executed terminal status")

    try:
        validate_execution_result_artifact(execution_result_artifact)
    except ExecutionResultArtifactValidationError:
        reason_code = "reentry_blocked_invalid_artifact"
        blocking_conditions.append("execution result artifact failed schema validation")

    try:
        validate_execution_gating_decision_artifact(gating_decision_artifact)
    except ExecutionGatingArtifactValidationError:
        reason_code = "reentry_blocked_invalid_artifact"
        blocking_conditions.append("gating decision artifact failed schema validation")

    if execution_result_artifact_path != work_item.get("execution_result_artifact_path"):
        reason_code = "reentry_blocked_invalid_lineage"
        blocking_conditions.append("execution result artifact path mismatch with work item")

    if gating_decision_artifact_path != work_item.get("gating_decision_artifact_path"):
        reason_code = "reentry_blocked_invalid_lineage"
        blocking_conditions.append("gating decision artifact path mismatch with work item")

    if execution_result_artifact.get("work_item_id") != work_item.get("work_item_id"):
        reason_code = "reentry_blocked_invalid_lineage"
        blocking_conditions.append("execution result work_item_id does not match work item")

    if gating_decision_artifact.get("work_item_id") != work_item.get("work_item_id"):
        reason_code = "reentry_blocked_invalid_lineage"
        blocking_conditions.append("gating decision work_item_id does not match work item")

    if execution_result_artifact.get("gating_decision_artifact_path") != gating_decision_artifact_path:
        reason_code = "reentry_blocked_invalid_lineage"
        blocking_conditions.append("execution result gating artifact path does not match gating lineage")

    if execution_result_artifact.get("repair_prompt_artifact_path") != work_item.get("repair_prompt_artifact_path"):
        reason_code = "reentry_blocked_invalid_lineage"
        blocking_conditions.append("execution result repair prompt lineage does not match work item")

    if gating_decision_artifact.get("repair_prompt_artifact_path") != work_item.get("repair_prompt_artifact_path"):
        reason_code = "reentry_blocked_invalid_lineage"
        blocking_conditions.append("gating decision repair prompt lineage does not match work item")

    if execution_result_artifact.get("parent_work_item_id") != work_item.get("parent_work_item_id"):
        reason_code = "reentry_blocked_invalid_lineage"
        blocking_conditions.append("execution result parent_work_item_id does not match work item")

    if gating_decision_artifact.get("parent_work_item_id") != work_item.get("parent_work_item_id"):
        reason_code = "reentry_blocked_invalid_lineage"
        blocking_conditions.append("gating decision parent_work_item_id does not match work item")

    execution_status = str(execution_result_artifact.get("execution_status") or "failure")
    generation = int(work_item.get("repair_loop_generation") or 0)

    review_trigger_recommended = False
    if not blocking_conditions:
        if execution_status == "success":
            decision_status = "complete"
            reason_code = "complete_execution_success"
        elif generation >= policy.max_generation_allowed:
            decision_status = "reentry_blocked"
            reason_code = "reentry_blocked_generation_limit_reached"
        else:
            decision_status = "review_required"
            reason_code = "review_required_execution_failure_within_generation_limit"
            review_trigger_recommended = True

    return _decision_artifact(
        work_item=work_item,
        execution_result_artifact_path=execution_result_artifact_path,
        gating_decision_artifact_path=gating_decision_artifact_path,
        decision_status=decision_status,
        reason_code=reason_code,
        execution_status=execution_status,
        max_generation_allowed=policy.max_generation_allowed,
        approval_required=approval_required,
        approval_present=approval_present,
        policy=policy,
        source_queue_state_path=source_queue_state_path,
        blocking_conditions=blocking_conditions,
        warnings=warnings,
        review_trigger_recommended=review_trigger_recommended,
        clock=clock,
    )


def _decision_artifact(
    *,
    work_item: dict,
    execution_result_artifact_path: str,
    gating_decision_artifact_path: str,
    decision_status: str,
    reason_code: str,
    execution_status: str,
    max_generation_allowed: int,
    approval_required: bool,
    approval_present: bool,
    policy: PostExecutionPolicyConfig,
    source_queue_state_path: str | None,
    blocking_conditions: list[str],
    warnings: list[str],
    review_trigger_recommended: bool,
    clock,
) -> dict:
    generated_at = iso_now(clock)
    artifact = {
        "post_execution_decision_artifact_id": f"postexec-{work_item.get('work_item_id', 'unknown')}-{generated_at}",
        "work_item_id": work_item.get("work_item_id"),
        "parent_work_item_id": work_item.get("parent_work_item_id"),
        "execution_result_artifact_path": execution_result_artifact_path,
        "gating_decision_artifact_path": gating_decision_artifact_path,
        "repair_prompt_artifact_path": work_item.get("repair_prompt_artifact_path"),
        "decision_status": decision_status,
        "decision_reason_code": reason_code,
        "execution_status": execution_status,
        "repair_loop_generation": int(work_item.get("repair_loop_generation") or 0),
        "max_generation_allowed": max_generation_allowed,
        "approval_required": approval_required,
        "approval_present": approval_present,
        "generated_at": generated_at,
        "generator_version": policy.generator_version,
        "blocking_conditions": blocking_conditions,
        "warnings": warnings,
        "source_queue_state_path": source_queue_state_path,
        "review_trigger_recommended": review_trigger_recommended,
    }
    validate_post_execution_decision_artifact(artifact)
    return artifact


def default_post_execution_decision_path(work_item_id: str, queue_state_path: Path) -> Path:
    stem = queue_state_path.stem
    return queue_state_path.parent / "post_execution_decisions" / f"{stem}.{work_item_id}.post_execution_decision.json"
