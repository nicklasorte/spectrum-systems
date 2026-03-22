"""Pure deterministic execution gating policy for governed prompt queue repair children."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from spectrum_systems.modules.prompt_queue.execution_gating_artifact_io import (
    validate_execution_gating_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.queue_artifact_io import ArtifactValidationError, validate_work_item
from spectrum_systems.modules.prompt_queue.queue_models import WorkItemStatus, iso_now, utc_now
from spectrum_systems.modules.prompt_queue.repair_prompt_artifact_io import (
    RepairPromptArtifactValidationError,
    validate_repair_prompt_artifact,
)


@dataclass(frozen=True)
class ExecutionGatingPolicyConfig:
    max_generation_allowed: int = 2
    approval_required_risk_levels: tuple[str, ...] = ("high", "critical")
    gating_policy_id: str = "prompt_queue_execution_gating_policy.v1"
    generator_version: str = "prompt_queue_execution_gating_policy.v1"


def _lineage_summary(work_item: dict) -> dict:
    return {
        "has_parent": bool(work_item.get("parent_work_item_id")),
        "has_repair_prompt_lineage": bool(work_item.get("spawned_from_repair_prompt_artifact_path")),
        "has_findings_lineage": bool(work_item.get("spawned_from_findings_artifact_path")),
        "has_review_lineage": bool(work_item.get("spawned_from_review_artifact_path")),
    }


def evaluate_execution_gating_policy(
    *,
    work_item: dict,
    repair_prompt_artifact: dict,
    repair_prompt_artifact_path: str,
    approval_present: bool,
    source_queue_state_path: str | None,
    policy: ExecutionGatingPolicyConfig = ExecutionGatingPolicyConfig(),
    clock=utc_now,
) -> dict:
    blocking_conditions: list[str] = []
    warnings: list[str] = []
    lineage = _lineage_summary(work_item)

    decision_status = "blocked"
    reason_code = "blocked_missing_required_input"

    try:
        validate_work_item(work_item)
    except ArtifactValidationError:
        reason_code = "blocked_invalid_work_item"
        blocking_conditions.append("work_item failed schema validation")
        return _decision_artifact(
            work_item=work_item,
            repair_prompt_artifact=repair_prompt_artifact,
            repair_prompt_artifact_path=repair_prompt_artifact_path,
            decision_status=decision_status,
            reason_code=reason_code,
            approval_required=False,
            approval_present=approval_present,
            policy=policy,
            lineage_summary=lineage,
            blocking_conditions=blocking_conditions,
            warnings=warnings,
            source_queue_state_path=source_queue_state_path,
            clock=clock,
        )

    if work_item.get("status") != WorkItemStatus.REPAIR_CHILD_CREATED.value:
        reason_code = "blocked_ineligible_status"
        blocking_conditions.append("work_item is not eligible for execution gating")

    if not lineage["has_parent"]:
        reason_code = "blocked_invalid_lineage"
        blocking_conditions.append("missing parent_work_item_id lineage")

    if not lineage["has_repair_prompt_lineage"]:
        reason_code = "blocked_invalid_lineage"
        blocking_conditions.append("missing repair prompt lineage")

    if not lineage["has_findings_lineage"]:
        reason_code = "blocked_invalid_lineage"
        blocking_conditions.append("missing findings lineage")

    if not lineage["has_review_lineage"]:
        reason_code = "blocked_invalid_lineage"
        blocking_conditions.append("missing review lineage")

    if not repair_prompt_artifact_path:
        blocking_conditions.append("missing repair prompt artifact path input")

    if work_item.get("spawned_from_repair_prompt_artifact_path") != repair_prompt_artifact_path:
        reason_code = "blocked_invalid_lineage"
        blocking_conditions.append("work_item repair prompt lineage path does not match gating input")

    try:
        validate_repair_prompt_artifact(repair_prompt_artifact)
    except RepairPromptArtifactValidationError:
        reason_code = "blocked_invalid_repair_prompt_artifact"
        blocking_conditions.append("repair prompt artifact failed schema validation")
    else:
        if repair_prompt_artifact.get("work_item_id") != work_item.get("parent_work_item_id"):
            reason_code = "blocked_invalid_lineage"
            blocking_conditions.append("repair prompt artifact work_item_id does not match parent lineage")

    generation = int(work_item.get("repair_loop_generation") or 0)
    if generation > policy.max_generation_allowed:
        reason_code = "blocked_generation_limit_exceeded"
        blocking_conditions.append(
            f"repair loop generation {generation} exceeds max allowed {policy.max_generation_allowed}"
        )

    risk_level = str(work_item.get("risk_level") or "")
    approval_required = risk_level in policy.approval_required_risk_levels

    if blocking_conditions:
        decision_status = "blocked"
    elif approval_required and not approval_present:
        decision_status = "approval_required"
        reason_code = "approval_required_high_risk"
    else:
        decision_status = "runnable"
        reason_code = "runnable_within_policy"

    return _decision_artifact(
        work_item=work_item,
        repair_prompt_artifact=repair_prompt_artifact,
        repair_prompt_artifact_path=repair_prompt_artifact_path,
        decision_status=decision_status,
        reason_code=reason_code,
        approval_required=approval_required,
        approval_present=approval_present,
        policy=policy,
        lineage_summary=lineage,
        blocking_conditions=blocking_conditions,
        warnings=warnings,
        source_queue_state_path=source_queue_state_path,
        clock=clock,
    )


def _decision_artifact(
    *,
    work_item: dict,
    repair_prompt_artifact: dict,
    repair_prompt_artifact_path: str,
    decision_status: str,
    reason_code: str,
    approval_required: bool,
    approval_present: bool,
    policy: ExecutionGatingPolicyConfig,
    lineage_summary: dict,
    blocking_conditions: list[str],
    warnings: list[str],
    source_queue_state_path: str | None,
    clock,
) -> dict:
    generated_at = iso_now(clock)
    artifact = {
        "gating_decision_artifact_id": f"gating-{work_item.get('work_item_id', 'unknown')}-{generated_at}",
        "work_item_id": work_item.get("work_item_id"),
        "parent_work_item_id": work_item.get("parent_work_item_id"),
        "repair_prompt_artifact_path": repair_prompt_artifact_path,
        "findings_artifact_path": work_item.get("spawned_from_findings_artifact_path"),
        "review_artifact_path": work_item.get("spawned_from_review_artifact_path"),
        "repair_loop_generation": int(work_item.get("repair_loop_generation") or 0),
        "risk_level": work_item.get("risk_level"),
        "decision_status": decision_status,
        "decision_reason_code": reason_code,
        "approval_required": approval_required,
        "approval_present": approval_present,
        "max_generation_allowed": policy.max_generation_allowed,
        "gating_policy_id": policy.gating_policy_id,
        "generated_at": generated_at,
        "generator_version": policy.generator_version,
        "blocking_conditions": blocking_conditions,
        "warnings": warnings,
        "lineage_summary": lineage_summary,
        "source_queue_state_path": source_queue_state_path,
    }
    # fail closed if output cannot validate
    validate_execution_gating_decision_artifact(artifact)
    return artifact


def default_execution_gating_decision_path(work_item_id: str, queue_state_path: Path) -> Path:
    stem = queue_state_path.stem
    return queue_state_path.parent / "gating" / f"{stem}.{work_item_id}.execution_gating_decision.json"
