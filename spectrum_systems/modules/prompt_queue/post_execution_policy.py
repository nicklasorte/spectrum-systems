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


class TransitionDecisionBuildError(ValueError):
    """Raised when unified transition decision generation fails closed."""


def _as_sorted_unique(values: list[str]) -> list[str]:
    return sorted(dict.fromkeys(values))


def build_queue_transition_decision(step_decision: dict, batch_decision_artifact: dict, findings_handoff: dict | None = None, *, clock=utc_now) -> dict:
    """Build a unified fail-closed queue transition decision artifact from QUEUE-03 outputs."""
    if not isinstance(step_decision, dict):
        raise TransitionDecisionBuildError("missing prompt_queue_step_decision artifact")
    if not isinstance(batch_decision_artifact, dict):
        raise TransitionDecisionBuildError("missing batch_decision_artifact")
    if batch_decision_artifact.get("artifact_type") != "batch_decision_artifact":
        raise TransitionDecisionBuildError("invalid batch_decision_artifact type")

    step_id = step_decision.get("step_id")
    source_decision_ref = step_decision.get("decision_id")
    if not step_id:
        raise TransitionDecisionBuildError("missing required lineage: step_id")
    if not source_decision_ref:
        raise TransitionDecisionBuildError("missing required lineage: source decision reference")

    queue_id = step_decision.get("queue_id")
    trace_linkage = step_decision.get("trace_linkage")
    if not queue_id and not trace_linkage:
        raise TransitionDecisionBuildError("missing required lineage: queue_id or trace_linkage")

    raw_decision = step_decision.get("decision")
    if raw_decision not in {"allow", "warn", "block"}:
        raise TransitionDecisionBuildError("unsupported step decision value")

    reason_codes = set(step_decision.get("reason_codes") or [])
    blocking_reasons = list(step_decision.get("blocking_reasons") or [])

    candidates: list[tuple[str, str, str]] = []
    if raw_decision == "allow":
        candidates.append(("continue", "allowed", "allow_clean_findings_continue"))
    if raw_decision == "warn":
        candidates.append(("request_review", "allowed", "warn_findings_request_review"))
    if raw_decision == "block" and findings_handoff is not None:
        handoff_status = findings_handoff.get("handoff_status")
        handoff_reason = findings_handoff.get("handoff_reason_code")
        if handoff_status == "handoff_completed" and handoff_reason == "handoff_completed_findings_emitted":
            candidates.append(("reenter_with_findings", "allowed", "block_findings_reenter_with_handoff"))
        elif handoff_status in {"handoff_failed", "handoff_blocked"}:
            candidates.append(("block", "blocked", "blocked_conflicting_inputs"))
            blocking_reasons.append("invalid_handoff")
        else:
            raise TransitionDecisionBuildError("ambiguous handoff status")

    if raw_decision == "block" and "errors_detected" in reason_codes and findings_handoff is None:
        candidates.append(("retry_allowed", "allowed", "block_errors_retry_allowed"))

    if raw_decision == "block" and "ambiguity_detected" in reason_codes:
        candidates.append(("block", "blocked", "block_ambiguity_fail_closed"))
        blocking_reasons.append("ambiguous_transition")

    if raw_decision == "block" and "invalid_report" in reason_codes:
        candidates.append(("block", "blocked", "block_invalid_report_fail_closed"))
        blocking_reasons.append("conflicting_signals")

    if not candidates:
        raise TransitionDecisionBuildError("no transition action inferred")

    unique_actions = {(action, status, code) for action, status, code in candidates}
    if len(unique_actions) > 1:
        raise TransitionDecisionBuildError("more than one transition action inferred")

    transition_action, transition_status, transition_reason_code = next(iter(unique_actions))
    if transition_status not in {"allowed", "blocked"}:
        raise TransitionDecisionBuildError("ambiguous transition status")

    derived = list(step_decision.get("derived_from_artifacts") or [])
    if findings_handoff is not None:
        derived.extend(
            [
                findings_handoff.get("review_parsing_handoff_artifact_id", ""),
                findings_handoff.get("findings_artifact_path", ""),
                findings_handoff.get("review_invocation_result_artifact_path", ""),
            ]
        )
    derived = [item for item in derived if item]
    if not derived:
        raise TransitionDecisionBuildError("missing required lineage: derived_from_artifacts")

    timestamp = iso_now(clock)
    artifact = {
        "transition_decision_id": f"transition-decision-{step_id}-{timestamp.replace('-', '').replace(':', '')}",
        "step_id": step_id,
        "queue_id": queue_id,
        "trace_linkage": trace_linkage,
        "source_decision_ref": source_decision_ref,
        "batch_decision_artifact_ref": batch_decision_artifact.get("batch_id"),
        "transition_action": transition_action,
        "transition_status": transition_status,
        "reason_codes": [transition_reason_code],
        "blocking_reasons": _as_sorted_unique(blocking_reasons if transition_status == "blocked" else []),
        "derived_from_artifacts": _as_sorted_unique(derived),
        "timestamp": timestamp,
    }

    from spectrum_systems.modules.prompt_queue.prompt_queue_transition_artifact_io import (
        validate_prompt_queue_transition_decision_artifact,
    )

    validate_prompt_queue_transition_decision_artifact(artifact)
    return artifact
