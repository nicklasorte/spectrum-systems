"""Pure deterministic policy for triggering governed review cycles."""

from __future__ import annotations

from dataclasses import dataclass

from spectrum_systems.modules.prompt_queue.loop_control_artifact_io import (
    LoopControlArtifactValidationError,
    validate_loop_control_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.post_execution_artifact_io import (
    PostExecutionArtifactValidationError,
    validate_post_execution_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.queue_artifact_io import ArtifactValidationError, validate_work_item
from spectrum_systems.modules.prompt_queue.queue_models import iso_now, utc_now
from spectrum_systems.modules.prompt_queue.review_trigger_artifact_io import validate_review_trigger_artifact


_SENSITIVE_SCOPE_MARKERS = (
    "control_loop",
    "evaluation_control",
    "certification",
    "pqx",
    "replay",
    "determinism",
    "roadmap",
    "contracts/schemas",
)


@dataclass(frozen=True)
class ReviewTriggerPolicyConfig:
    generator_version: str = "prompt_queue_review_trigger_policy.v2"


def _contains_sensitive_scope(work_item: dict) -> bool:
    scope_paths = [str(p).lower() for p in (work_item.get("scope_paths") or [])]
    return any(marker in path for marker in _SENSITIVE_SCOPE_MARKERS for path in scope_paths)


def _derive_review_type(work_item: dict, post_execution_decision_artifact: dict, loop_control_decision_artifact: dict | None) -> str:
    prompt_id = str(work_item.get("prompt_id") or "").lower()
    title = str(work_item.get("title") or "").lower()
    post_reason = str(post_execution_decision_artifact.get("decision_reason_code") or "").lower()
    loop_reason = str((loop_control_decision_artifact or {}).get("reason_code") or "").lower()

    if _contains_sensitive_scope(work_item):
        return "surgical"
    if "hard_gate" in prompt_id or "hard gate" in title or "major_capability" in post_reason or "promotion" in title:
        return "hard_gate"
    if "strategic" in prompt_id or "program" in prompt_id or "roadmap" in title:
        return "strategic"
    if "fail" in post_reason or "blocked" in post_reason or "limit_exceeded" in loop_reason:
        return "failure"
    if work_item.get("parent_work_item_id") is None:
        return "batch_architecture"
    return "failure"


def _build_review_request(*, work_item: dict, post_execution_decision_artifact: dict, generated_at: str) -> dict:
    review_type = _derive_review_type(work_item, post_execution_decision_artifact, None)
    return {
        "review_id": f"rr-{work_item.get('work_item_id', 'unknown')}-{generated_at}",
        "review_type": review_type,
        "scope_refs": sorted(dict.fromkeys(work_item.get("scope_paths") or [])),
        "triggering_event": str(post_execution_decision_artifact.get("decision_reason_code") or "review_required"),
        "required": True,
        "blocking": True,
        "related_batch_id": str(work_item.get("parent_work_item_id") or work_item.get("work_item_id") or ""),
        "slice_id": str(work_item.get("work_item_id") or ""),
        "program_id": str(work_item.get("prompt_id") or ""),
        "created_at": generated_at,
        "trace_id": f"trace::{work_item.get('work_item_id', 'unknown')}",
        "source_refs": [
            str(work_item.get("post_execution_decision_artifact_path") or ""),
            str(work_item.get("execution_result_artifact_path") or ""),
        ],
    }


def evaluate_review_trigger_policy(
    *,
    work_item: dict,
    post_execution_decision_artifact: dict,
    post_execution_decision_artifact_path: str,
    loop_control_decision_artifact: dict | None,
    loop_control_decision_artifact_path: str | None,
    execution_result_artifact_path: str,
    source_queue_state_path: str | None,
    config: ReviewTriggerPolicyConfig = ReviewTriggerPolicyConfig(),
    clock=utc_now,
) -> dict:
    blocking_conditions: list[str] = []
    warnings: list[str] = []

    trigger_status = "blocked_no_trigger"
    trigger_reason_code = "blocked_invalid_artifact"

    try:
        validate_work_item(work_item)
    except ArtifactValidationError:
        blocking_conditions.append("work_item failed schema validation")
        return _build_artifact(
            work_item=work_item,
            post_execution_decision_artifact=post_execution_decision_artifact,
            post_execution_decision_artifact_path=post_execution_decision_artifact_path,
            loop_control_decision_artifact_path=loop_control_decision_artifact_path,
            execution_result_artifact_path=execution_result_artifact_path,
            trigger_status=trigger_status,
            trigger_reason_code=trigger_reason_code,
            source_queue_state_path=source_queue_state_path,
            blocking_conditions=blocking_conditions,
            warnings=warnings,
            config=config,
            clock=clock,
        )

    try:
        validate_post_execution_decision_artifact(post_execution_decision_artifact)
    except PostExecutionArtifactValidationError:
        blocking_conditions.append("post-execution decision artifact failed schema validation")
        return _build_artifact(
            work_item=work_item,
            post_execution_decision_artifact=post_execution_decision_artifact,
            post_execution_decision_artifact_path=post_execution_decision_artifact_path,
            loop_control_decision_artifact_path=loop_control_decision_artifact_path,
            execution_result_artifact_path=execution_result_artifact_path,
            trigger_status=trigger_status,
            trigger_reason_code=trigger_reason_code,
            source_queue_state_path=source_queue_state_path,
            blocking_conditions=blocking_conditions,
            warnings=warnings,
            config=config,
            clock=clock,
        )

    if loop_control_decision_artifact is not None:
        try:
            validate_loop_control_decision_artifact(loop_control_decision_artifact)
        except LoopControlArtifactValidationError:
            blocking_conditions.append("loop-control decision artifact failed schema validation")
            return _build_artifact(
                work_item=work_item,
                post_execution_decision_artifact=post_execution_decision_artifact,
                post_execution_decision_artifact_path=post_execution_decision_artifact_path,
                loop_control_decision_artifact_path=loop_control_decision_artifact_path,
                execution_result_artifact_path=execution_result_artifact_path,
                trigger_status=trigger_status,
                trigger_reason_code=trigger_reason_code,
                source_queue_state_path=source_queue_state_path,
                blocking_conditions=blocking_conditions,
                warnings=warnings,
                config=config,
                clock=clock,
            )

    if post_execution_decision_artifact.get("work_item_id") != work_item.get("work_item_id"):
        blocking_conditions.append("post-execution decision work_item_id mismatch")
    if post_execution_decision_artifact.get("parent_work_item_id") != work_item.get("parent_work_item_id"):
        blocking_conditions.append("post-execution decision parent_work_item_id mismatch")
    if post_execution_decision_artifact_path != work_item.get("post_execution_decision_artifact_path"):
        blocking_conditions.append("post-execution decision artifact path mismatch")
    if execution_result_artifact_path != work_item.get("execution_result_artifact_path"):
        blocking_conditions.append("execution result artifact path mismatch with work item")
    if post_execution_decision_artifact.get("execution_result_artifact_path") != execution_result_artifact_path:
        blocking_conditions.append("post-execution execution_result_artifact_path mismatch")

    if loop_control_decision_artifact_path:
        if loop_control_decision_artifact is None:
            blocking_conditions.append("loop-control artifact path provided without artifact payload")
        if loop_control_decision_artifact_path != work_item.get("loop_control_decision_artifact_path"):
            blocking_conditions.append("loop-control decision artifact path mismatch")
    if loop_control_decision_artifact is not None:
        if loop_control_decision_artifact.get("work_item_id") != work_item.get("work_item_id"):
            blocking_conditions.append("loop-control decision work_item_id mismatch")
        if loop_control_decision_artifact.get("parent_work_item_id") != work_item.get("parent_work_item_id"):
            blocking_conditions.append("loop-control decision parent_work_item_id mismatch")
        if loop_control_decision_artifact_path is None:
            blocking_conditions.append("loop-control decision artifact path missing")

    if blocking_conditions:
        return _build_artifact(
            work_item=work_item,
            post_execution_decision_artifact=post_execution_decision_artifact,
            post_execution_decision_artifact_path=post_execution_decision_artifact_path,
            loop_control_decision_artifact_path=loop_control_decision_artifact_path,
            execution_result_artifact_path=execution_result_artifact_path,
            trigger_status="blocked_no_trigger",
            trigger_reason_code="blocked_invalid_lineage",
            source_queue_state_path=source_queue_state_path,
            blocking_conditions=blocking_conditions,
            warnings=warnings,
            config=config,
            clock=clock,
        )

    post_status = post_execution_decision_artifact.get("decision_status")
    loop_action = (loop_control_decision_artifact or {}).get("enforcement_action")

    if post_status == "complete":
        trigger_status = "no_review_needed"
        trigger_reason_code = "no_review_needed_post_execution_complete"
    elif post_status == "reentry_blocked":
        trigger_status = "blocked_no_trigger"
        trigger_reason_code = "blocked_post_execution_reentry_blocked"
    elif loop_action == "block_reentry":
        trigger_status = "blocked_no_trigger"
        trigger_reason_code = "blocked_loop_control_block_reentry"
    elif post_status == "review_required" and loop_action in {None, "allow_reentry", "require_review"}:
        trigger_status = "review_triggered"
        trigger_reason_code = "review_triggered_post_execution_review_required"
    else:
        trigger_status = "blocked_no_trigger"
        trigger_reason_code = "blocked_policy_ineligible"

    return _build_artifact(
        work_item=work_item,
        post_execution_decision_artifact=post_execution_decision_artifact,
        post_execution_decision_artifact_path=post_execution_decision_artifact_path,
        loop_control_decision_artifact_path=loop_control_decision_artifact_path,
        execution_result_artifact_path=execution_result_artifact_path,
        trigger_status=trigger_status,
        trigger_reason_code=trigger_reason_code,
        source_queue_state_path=source_queue_state_path,
        blocking_conditions=blocking_conditions,
        warnings=warnings,
        config=config,
        clock=clock,
    )


def _build_artifact(
    *,
    work_item: dict,
    post_execution_decision_artifact: dict,
    post_execution_decision_artifact_path: str,
    loop_control_decision_artifact_path: str | None,
    execution_result_artifact_path: str,
    trigger_status: str,
    trigger_reason_code: str,
    source_queue_state_path: str | None,
    blocking_conditions: list[str],
    warnings: list[str],
    config: ReviewTriggerPolicyConfig,
    clock,
) -> dict:
    generated_at = iso_now(clock)
    review_request = _build_review_request(
        work_item=work_item,
        post_execution_decision_artifact=post_execution_decision_artifact,
        generated_at=generated_at,
    ) if trigger_status == "review_triggered" else None
    artifact = {
        "review_trigger_artifact_id": f"review-trigger-{work_item.get('work_item_id', 'unknown')}-{generated_at}",
        "work_item_id": work_item.get("work_item_id"),
        "parent_work_item_id": work_item.get("parent_work_item_id"),
        "post_execution_decision_artifact_path": post_execution_decision_artifact_path,
        "loop_control_decision_artifact_path": loop_control_decision_artifact_path,
        "execution_result_artifact_path": execution_result_artifact_path,
        "trigger_status": trigger_status,
        "trigger_reason_code": trigger_reason_code,
        "generated_at": generated_at,
        "generator_version": config.generator_version,
        "spawned_review_work_item_id": None,
        "source_queue_state_path": source_queue_state_path,
        "warnings": warnings,
        "blocking_conditions": blocking_conditions,
        "review_request": review_request,
    }
    validate_review_trigger_artifact(artifact)
    return artifact


def derive_review_trigger_from_transition(transition_decision_artifact: dict) -> dict:
    """Map unified transition decision to deterministic review trigger posture."""
    from spectrum_systems.modules.prompt_queue.prompt_queue_transition_artifact_io import (
        validate_prompt_queue_transition_decision_artifact,
    )

    validate_prompt_queue_transition_decision_artifact(transition_decision_artifact)
    action = transition_decision_artifact["transition_action"]
    if action == "request_review":
        return {"trigger_status": "review_triggered", "trigger_reason_code": "review_triggered_post_execution_review_required"}
    if action == "block":
        return {"trigger_status": "blocked_no_trigger", "trigger_reason_code": "blocked_policy_ineligible"}
    return {"trigger_status": "no_review_needed", "trigger_reason_code": "no_review_needed_post_execution_complete"}
