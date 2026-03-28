"""Governed prompt queue MVP module."""

from spectrum_systems.modules.prompt_queue.blocked_recovery_artifact_io import (
    BlockedRecoveryArtifactIOError,
    BlockedRecoveryArtifactValidationError,
    default_blocked_recovery_decision_path,
    validate_blocked_recovery_decision_artifact,
    write_blocked_recovery_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.blocked_recovery_policy import (
    BlockedRecoveryPolicyConfig,
    BlockedRecoveryPolicyError,
    evaluate_blocked_recovery_policy,
)
from spectrum_systems.modules.prompt_queue.blocked_recovery_queue_integration import (
    BlockedRecoveryQueueIntegrationError,
    apply_blocked_recovery_decision_to_queue,
)
from spectrum_systems.modules.prompt_queue.retry_artifact_io import (
    RetryArtifactIOError,
    RetryArtifactValidationError,
    default_retry_decision_path,
    validate_retry_decision_artifact,
    write_retry_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.retry_policy import (
    RetryPolicyConfig,
    RetryPolicyError,
    evaluate_retry_policy,
)
from spectrum_systems.modules.prompt_queue.retry_queue_integration import (
    RetryQueueIntegrationError,
    apply_retry_decision_to_queue,
)
from spectrum_systems.modules.prompt_queue.execution_artifact_io import (
    default_execution_result_path,
    read_execution_result_artifact,
    validate_execution_result_artifact,
    write_execution_result_artifact,
)
from spectrum_systems.modules.prompt_queue.execution_queue_integration import (
    ExecutionQueueIntegrationError,
    finalize_execution,
    run_queue_step_execution_adapter,
    transition_to_executing,
)
from spectrum_systems.modules.prompt_queue.execution_runner import (
    ExecutionRunnerError,
    revalidate_execution_entry,
    run_queue_step_execution,
    run_simulated_execution,
)
from spectrum_systems.modules.prompt_queue.execution_gating_artifact_io import (
    validate_execution_gating_decision_artifact,
    write_execution_gating_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.execution_gating_policy import (
    ExecutionGatingPolicyConfig,
    default_execution_gating_decision_path,
    evaluate_execution_gating_policy,
)
from spectrum_systems.modules.prompt_queue.execution_gating_queue_integration import (
    ExecutionGatingQueueIntegrationError,
    apply_execution_gating_decision_to_queue,
)
from spectrum_systems.modules.prompt_queue.loop_control_artifact_io import (
    default_loop_control_decision_path,
    validate_loop_control_decision_artifact,
    write_loop_control_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.loop_control_policy import (
    LoopControlPolicyConfig,
    LoopControlPolicyError,
    evaluate_loop_control_policy,
)
from spectrum_systems.modules.prompt_queue.loop_control_queue_integration import (
    LoopControlQueueIntegrationError,
    emit_loop_control_transition_receipt,
)
from spectrum_systems.modules.prompt_queue.loop_continuation import LoopContinuationError, run_loop_continuation
from spectrum_systems.modules.prompt_queue.loop_continuation_artifact_io import (
    LoopContinuationArtifactIOError,
    default_loop_continuation_path,
    write_loop_continuation_artifact,
)
from spectrum_systems.modules.prompt_queue.loop_continuation_queue_integration import (
    LoopContinuationQueueIntegrationError,
    apply_loop_continuation_to_queue,
)
from spectrum_systems.modules.prompt_queue.post_execution_artifact_io import (
    validate_post_execution_decision_artifact,
    write_post_execution_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.post_execution_policy import (
    PostExecutionPolicyConfig,
    TransitionDecisionBuildError,
    build_queue_transition_decision,
    default_post_execution_decision_path,
    evaluate_post_execution_policy,
)
from spectrum_systems.modules.prompt_queue.post_execution_queue_integration import (
    PostExecutionQueueIntegrationError,
    emit_post_execution_transition_receipt,
)
from spectrum_systems.modules.prompt_queue.review_trigger_artifact_io import (
    default_review_trigger_path,
    validate_review_trigger_artifact,
    write_review_trigger_artifact,
)
from spectrum_systems.modules.prompt_queue.review_trigger_policy import (
    ReviewTriggerPolicyConfig,
    evaluate_review_trigger_policy,
)
from spectrum_systems.modules.prompt_queue.review_trigger_queue_integration import (
    ReviewTriggerQueueIntegrationError,
    apply_review_trigger_to_queue,
)
from spectrum_systems.modules.prompt_queue.next_step_action_artifact_io import (
    default_next_step_action_path,
    validate_next_step_action_artifact,
    write_next_step_action_artifact,
)
from spectrum_systems.modules.prompt_queue.next_step_orchestrator import (
    NextStepOrchestrationConfig,
    NextStepOrchestrationError,
    determine_next_step_action,
)
from spectrum_systems.modules.prompt_queue.next_step_queue_integration import (
    NextStepQueueIntegrationError,
    emit_next_step_transition_receipt,
)
from spectrum_systems.modules.prompt_queue.findings_artifact_io import (
    validate_findings_artifact,
    write_findings_artifact,
)
from spectrum_systems.modules.prompt_queue.findings_reentry import FindingsReentryError, run_findings_reentry
from spectrum_systems.modules.prompt_queue.findings_reentry_artifact_io import (
    FindingsReentryArtifactIOError,
    default_findings_reentry_path,
    write_findings_reentry_artifact,
)
from spectrum_systems.modules.prompt_queue.findings_reentry_queue_integration import (
    FindingsReentryQueueIntegrationError,
    apply_findings_reentry_to_queue,
)
from spectrum_systems.modules.prompt_queue.findings_normalizer import (
    build_findings_artifact,
    default_findings_path,
)
from spectrum_systems.modules.prompt_queue.findings_queue_integration import attach_findings_to_work_item
from spectrum_systems.modules.prompt_queue.review_parsing_handoff import (
    ReviewParsingHandoffError,
    run_review_parsing_handoff,
)
from spectrum_systems.modules.prompt_queue.review_parsing_handoff_artifact_io import (
    ReviewParsingHandoffArtifactIOError,
    default_review_parsing_handoff_path,
    write_review_parsing_handoff_artifact,
)
from spectrum_systems.modules.prompt_queue.review_parsing_handoff_queue_integration import (
    ReviewParsingHandoffQueueIntegrationError,
    apply_review_parsing_handoff_to_queue,
)
from spectrum_systems.modules.prompt_queue.repair_prompt_artifact_io import (
    validate_repair_prompt_artifact,
    write_repair_prompt_artifact,
)
from spectrum_systems.modules.prompt_queue.repair_prompt_generator import (
    RepairPromptGenerationError,
    default_repair_prompt_path,
    generate_repair_prompt_artifact,
)
from spectrum_systems.modules.prompt_queue.repair_prompt_queue_integration import (
    attach_repair_prompt_to_work_item,
)
from spectrum_systems.modules.prompt_queue.repair_child_creator import (
    RepairChildCreationError,
    build_repair_child_work_item,
)
from spectrum_systems.modules.prompt_queue.repair_child_queue_integration import (
    RepairChildQueueIntegrationError,
    spawn_repair_child_in_queue,
)
from spectrum_systems.modules.prompt_queue.queue_artifact_io import (
    validate_findings_reentry,
    validate_loop_continuation,
    validate_observability_snapshot,
    validate_queue_state,
    validate_review_parsing_handoff,
    validate_review_invocation_result,
    validate_review_attempt,
    validate_work_item,
    write_artifact,
)
from spectrum_systems.modules.prompt_queue.queue_observability import (
    generate_queue_snapshot,
    validate_queue_invariants,
)
from spectrum_systems.modules.prompt_queue.queue_models import (
    Priority,
    RiskLevel,
    WorkItemStatus,
    make_queue_state,
    make_work_item,
)
from spectrum_systems.modules.prompt_queue.queue_state_machine import IllegalTransitionError, transition_work_item
from spectrum_systems.modules.prompt_queue.review_parser import ReviewParseError, parse_queue_step_report, parse_review_markdown
from spectrum_systems.modules.prompt_queue.prompt_queue_transition_artifact_io import (
    PromptQueueTransitionArtifactValidationError,
    validate_prompt_queue_transition_decision_artifact,
    write_prompt_queue_transition_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.step_decision import (
    StepDecisionError,
    build_step_decision,
    default_step_decision_path,
    validate_step_decision_artifact,
)
from spectrum_systems.modules.prompt_queue.review_provider_orchestrator import ProviderResult, run_review_with_fallback
from spectrum_systems.modules.prompt_queue.review_invocation_entry_validation import (
    ReviewInvocationEntryValidationError,
    validate_review_invocation_entry,
)
from spectrum_systems.modules.prompt_queue.review_invocation_provider_adapter import (
    InvocationProviderOutcome,
    InvocationProviderResult,
    ReviewInvocationProviderError,
    invoke_review_provider,
)
from spectrum_systems.modules.prompt_queue.review_invocation_runner import (
    build_invocation_id,
    run_review_invocation_step_adapter,
    run_live_review_invocation,
)
from spectrum_systems.modules.prompt_queue.review_invocation_artifact_io import (
    ReviewInvocationArtifactIOError,
    default_review_invocation_result_path,
    write_review_invocation_result_artifact,
)
from spectrum_systems.modules.prompt_queue.review_invocation_queue_integration import (
    ReviewInvocationQueueIntegrationError,
    apply_live_review_invocation,
)
from spectrum_systems.modules.prompt_queue.review_invocation_guard import (
    DuplicateReviewInvocationError,
    assert_no_duplicate_review_invocation,
    has_duplicate_review_invocation_result,
)


def _compat_find_work_item(queue_state: dict, work_item_id: str) -> dict:
    for item in queue_state.get("work_items", []):
        if item.get("work_item_id") == work_item_id:
            return dict(item)
    raise ValueError(f"Work item '{work_item_id}' not found in queue state.")


def apply_post_execution_decision_to_queue(*, queue_state: dict, work_item_id: str, post_execution_decision_artifact: dict, post_execution_decision_artifact_path: str, clock=None):
    """Compatibility wrapper delegating to transition receipt integration (read-only)."""
    transition = {
        "transition_decision_id": f"compat-postexec-{work_item_id}",
        "step_id": work_item_id if work_item_id.startswith("step-") else "step-001",
        "queue_id": queue_state.get("queue_id"),
        "trace_linkage": queue_state.get("queue_id") or work_item_id,
        "source_decision_ref": post_execution_decision_artifact.get("post_execution_decision_artifact_id")
        or post_execution_decision_artifact_path,
        "transition_action": {
            "complete": "continue",
            "review_required": "request_review",
            "reentry_eligible": "reenter_with_findings",
            "reentry_blocked": "block",
        }.get(post_execution_decision_artifact.get("decision_status"), "block"),
        "transition_status": "blocked" if post_execution_decision_artifact.get("decision_status") == "reentry_blocked" else "allowed",
        "reason_codes": ["block_invalid_report_fail_closed"] if post_execution_decision_artifact.get("decision_status") == "reentry_blocked" else ["warn_findings_request_review"],
        "blocking_reasons": ["unsupported_decision"] if post_execution_decision_artifact.get("decision_status") == "reentry_blocked" else [],
        "derived_from_artifacts": [post_execution_decision_artifact.get("execution_result_artifact_path") or post_execution_decision_artifact_path],
        "timestamp": post_execution_decision_artifact.get("generated_at") or "2026-03-28T00:00:00Z",
    }
    emit_post_execution_transition_receipt(
        queue_state=queue_state,
        transition_decision_artifact=transition,
        transition_decision_artifact_path=post_execution_decision_artifact_path,
    )
    return queue_state, _compat_find_work_item(queue_state, work_item_id)


def apply_next_step_action_to_queue(*, queue_state: dict, work_item_id: str, next_step_action_artifact: dict, next_step_action_artifact_path: str, clock=None):
    """Compatibility wrapper delegating to transition receipt integration (read-only)."""
    transition = {
        "transition_decision_id": f"compat-nextstep-{work_item_id}",
        "step_id": work_item_id if work_item_id.startswith("step-") else "step-001",
        "queue_id": queue_state.get("queue_id"),
        "trace_linkage": queue_state.get("queue_id") or work_item_id,
        "source_decision_ref": next_step_action_artifact.get("execution_result_artifact_path") or next_step_action_artifact_path,
        "transition_action": {
            "marked_complete": "continue",
            "spawn_review": "request_review",
            "spawn_reentry_child": "reenter_with_findings",
            "blocked_no_action": "block",
        }.get(next_step_action_artifact.get("action_status"), "block"),
        "transition_status": "blocked" if next_step_action_artifact.get("action_status") == "blocked_no_action" else "allowed",
        "reason_codes": ["block_invalid_report_fail_closed"] if next_step_action_artifact.get("action_status") == "blocked_no_action" else ["warn_findings_request_review"],
        "blocking_reasons": ["unsupported_decision"] if next_step_action_artifact.get("action_status") == "blocked_no_action" else [],
        "derived_from_artifacts": [next_step_action_artifact.get("execution_result_artifact_path") or next_step_action_artifact_path],
        "timestamp": next_step_action_artifact.get("generated_at") or "2026-03-28T00:00:00Z",
    }
    receipt = emit_next_step_transition_receipt(
        queue_state=queue_state,
        transition_decision_artifact=transition,
        transition_decision_artifact_path=next_step_action_artifact_path,
    )
    updated_action = dict(next_step_action_artifact)
    updated_action.setdefault("spawned_work_item_id", None)
    updated_action.setdefault("warnings", [])
    updated_action.setdefault("blocking_conditions", [])
    updated_action["compatibility_receipt"] = receipt
    return queue_state, _compat_find_work_item(queue_state, work_item_id), None, updated_action


def apply_loop_control_decision_to_queue(*, queue_state: dict, work_item_id: str, loop_control_decision_artifact: dict, loop_control_decision_artifact_path: str, clock=None):
    """Compatibility wrapper delegating to transition receipt integration (read-only)."""
    transition = {
        "transition_decision_id": f"compat-loop-{work_item_id}",
        "step_id": work_item_id if work_item_id.startswith("step-") else "step-001",
        "queue_id": queue_state.get("queue_id"),
        "trace_linkage": queue_state.get("queue_id") or work_item_id,
        "source_decision_ref": loop_control_decision_artifact.get("loop_control_decision_artifact_id")
        or loop_control_decision_artifact_path,
        "transition_action": {
            "allow_reentry": "retry_allowed",
            "require_review": "reenter_with_findings",
            "block_reentry": "block",
        }.get(loop_control_decision_artifact.get("enforcement_action"), "block"),
        "transition_status": "blocked" if loop_control_decision_artifact.get("enforcement_action") == "block_reentry" else "allowed",
        "reason_codes": ["block_invalid_report_fail_closed"] if loop_control_decision_artifact.get("enforcement_action") == "block_reentry" else ["warn_findings_request_review"],
        "blocking_reasons": ["unsupported_decision"] if loop_control_decision_artifact.get("enforcement_action") == "block_reentry" else [],
        "derived_from_artifacts": [loop_control_decision_artifact.get("loop_control_decision_artifact_id") or loop_control_decision_artifact_path],
        "timestamp": loop_control_decision_artifact.get("generated_at") or "2026-03-28T00:00:00Z",
    }
    emit_loop_control_transition_receipt(
        queue_state=queue_state,
        transition_decision_artifact=transition,
        transition_decision_artifact_path=loop_control_decision_artifact_path,
    )
    return queue_state, _compat_find_work_item(queue_state, work_item_id)


__all__ = [
    "apply_blocked_recovery_decision_to_queue",
    "BlockedRecoveryQueueIntegrationError",
    "evaluate_blocked_recovery_policy",
    "BlockedRecoveryPolicyError",
    "BlockedRecoveryPolicyConfig",
    "write_blocked_recovery_decision_artifact",
    "validate_blocked_recovery_decision_artifact",
    "default_blocked_recovery_decision_path",
    "BlockedRecoveryArtifactValidationError",
    "BlockedRecoveryArtifactIOError",
    "apply_retry_decision_to_queue",
    "RetryQueueIntegrationError",
    "evaluate_retry_policy",
    "RetryPolicyError",
    "RetryPolicyConfig",
    "write_retry_decision_artifact",
    "validate_retry_decision_artifact",
    "default_retry_decision_path",
    "RetryArtifactValidationError",
    "RetryArtifactIOError",
    "default_execution_result_path",
    "read_execution_result_artifact",
    "validate_execution_result_artifact",
    "write_execution_result_artifact",
    "ExecutionQueueIntegrationError",
    "transition_to_executing",
    "run_queue_step_execution_adapter",
    "finalize_execution",
    "ExecutionRunnerError",
    "revalidate_execution_entry",
    "run_queue_step_execution",
    "run_simulated_execution",
    "write_execution_gating_decision_artifact",
    "validate_execution_gating_decision_artifact",
    "evaluate_execution_gating_policy",
    "default_execution_gating_decision_path",
    "apply_execution_gating_decision_to_queue",
    "ExecutionGatingQueueIntegrationError",
    "ExecutionGatingPolicyConfig",
    "write_loop_control_decision_artifact",
    "validate_loop_control_decision_artifact",
    "default_loop_control_decision_path",
    "evaluate_loop_control_policy",
    "LoopControlPolicyConfig",
    "LoopControlPolicyError",
    "emit_loop_control_transition_receipt",
    "apply_post_execution_decision_to_queue",
    "apply_next_step_action_to_queue",
    "apply_loop_control_decision_to_queue",
    "LoopControlQueueIntegrationError",
    "run_loop_continuation",
    "LoopContinuationError",
    "default_loop_continuation_path",
    "write_loop_continuation_artifact",
    "LoopContinuationArtifactIOError",
    "apply_loop_continuation_to_queue",
    "LoopContinuationQueueIntegrationError",
    "write_post_execution_decision_artifact",
    "write_review_trigger_artifact",
    "validate_review_trigger_artifact",
    "default_review_trigger_path",
    "ReviewTriggerPolicyConfig",
    "evaluate_review_trigger_policy",
    "ReviewTriggerQueueIntegrationError",
    "apply_review_trigger_to_queue",
    "validate_post_execution_decision_artifact",
    "evaluate_post_execution_policy",
    "default_post_execution_decision_path",
    "build_queue_transition_decision",
    "TransitionDecisionBuildError",
    "emit_post_execution_transition_receipt",
    "PostExecutionQueueIntegrationError",
    "PostExecutionPolicyConfig",
    "default_next_step_action_path",
    "validate_next_step_action_artifact",
    "write_next_step_action_artifact",
    "NextStepOrchestrationConfig",
    "NextStepOrchestrationError",
    "determine_next_step_action",
    "NextStepQueueIntegrationError",
    "emit_next_step_transition_receipt",
    "spawn_repair_child_in_queue",
    "RepairChildQueueIntegrationError",
    "build_repair_child_work_item",
    "RepairChildCreationError",
    "write_repair_prompt_artifact",
    "validate_repair_prompt_artifact",
    "generate_repair_prompt_artifact",
    "default_repair_prompt_path",
    "attach_repair_prompt_to_work_item",
    "RepairPromptGenerationError",
    "IllegalTransitionError",
    "Priority",
    "ProviderResult",
    "ReviewParseError",
    "DuplicateReviewInvocationError",
    "RiskLevel",
    "WorkItemStatus",
    "attach_findings_to_work_item",
    "run_findings_reentry",
    "FindingsReentryError",
    "default_findings_reentry_path",
    "write_findings_reentry_artifact",
    "FindingsReentryArtifactIOError",
    "apply_findings_reentry_to_queue",
    "FindingsReentryQueueIntegrationError",
    "apply_review_parsing_handoff_to_queue",
    "build_findings_artifact",
    "default_findings_path",
    "make_queue_state",
    "make_work_item",
    "parse_review_markdown",
    "run_review_with_fallback",
    "transition_work_item",
    "assert_no_duplicate_review_invocation",
    "has_duplicate_review_invocation_result",
    "validate_findings_artifact",
    "validate_findings_reentry",
    "generate_queue_snapshot",
    "validate_loop_continuation",
    "validate_observability_snapshot",
    "validate_queue_state",
    "validate_queue_invariants",
    "validate_review_parsing_handoff",
    "validate_review_invocation_result",
    "validate_review_attempt",
    "validate_work_item",
    "write_artifact",
    "write_findings_artifact",
    "ReviewInvocationEntryValidationError",
    "validate_review_invocation_entry",
    "InvocationProviderOutcome",
    "InvocationProviderResult",
    "ReviewInvocationProviderError",
    "invoke_review_provider",
    "build_invocation_id",
    "run_review_invocation_step_adapter",
    "run_live_review_invocation",
    "ReviewInvocationArtifactIOError",
    "default_review_invocation_result_path",
    "write_review_invocation_result_artifact",
    "ReviewInvocationQueueIntegrationError",
    "apply_live_review_invocation",
    "ReviewParsingHandoffError",
    "run_review_parsing_handoff",
    "ReviewParsingHandoffArtifactIOError",
    "default_review_parsing_handoff_path",
    "write_review_parsing_handoff_artifact",
    "ReviewParsingHandoffQueueIntegrationError",
    "parse_queue_step_report",
    "build_step_decision",
    "validate_step_decision_artifact",
    "default_step_decision_path",
    "build_queue_transition_decision",
    "PromptQueueTransitionArtifactValidationError",
    "write_prompt_queue_transition_decision_artifact",
    "validate_prompt_queue_transition_decision_artifact",
    "StepDecisionError",
]
