"""Models for the governed prompt queue MVP."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class WorkItemStatus(str, Enum):
    QUEUED = "queued"
    REVIEW_QUEUED = "review_queued"
    REVIEW_RUNNING = "review_running"
    REVIEW_PROVIDER_FAILED = "review_provider_failed"
    REVIEW_FALLBACK_RUNNING = "review_fallback_running"
    REVIEW_COMPLETE = "review_complete"
    FINDINGS_PARSED = "findings_parsed"
    REPAIR_PROMPT_GENERATED = "repair_prompt_generated"
    REPAIR_CHILD_CREATED = "repair_child_created"
    EXECUTION_GATED = "execution_gated"
    RUNNABLE = "runnable"
    EXECUTING = "executing"
    EXECUTED_SUCCESS = "executed_success"
    EXECUTED_FAILURE = "executed_failure"
    COMPLETE = "complete"
    REVIEW_REQUIRED = "review_required"
    REENTRY_BLOCKED = "reentry_blocked"
    REENTRY_ELIGIBLE = "reentry_eligible"
    REVIEW_TRIGGERED = "review_triggered"
    REVIEW_INVOKING = "review_invoking"
    REVIEW_INVOCATION_SUCCEEDED = "review_invocation_succeeded"
    REVIEW_INVOCATION_FAILED = "review_invocation_failed"
    APPROVAL_REQUIRED = "approval_required"
    BLOCKED = "blocked"


class QueueStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    BLOCKED = "blocked"
    COMPLETED = "completed"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReviewProvider(str, Enum):
    CLAUDE = "claude"
    CODEX = "codex"


class FallbackReason(str, Enum):
    USAGE_LIMIT = "usage_limit"
    RATE_LIMITED = "rate_limited"
    AUTH_FAILURE = "auth_failure"
    TIMEOUT = "timeout"
    PROVIDER_UNAVAILABLE = "provider_unavailable"


class ReviewOutcomeStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"


class QueueValidationError(ValueError):
    """Raised when queue model or schema validation fails."""


Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(tz=timezone.utc).replace(microsecond=0)


def iso_now(clock: Clock = utc_now) -> str:
    return clock().isoformat().replace("+00:00", "Z")


@dataclass
class WorkItem:
    work_item_id: str
    prompt_id: str
    title: str
    status: str
    priority: str
    risk_level: str
    repo: str
    branch: str
    scope_paths: list[str]
    review_provider_primary: str = ReviewProvider.CODEX.value
    review_provider_actual: Optional[str] = None
    review_attempt_count: int = 0
    review_fallback_used: bool = False
    review_fallback_reason: Optional[str] = None
    findings_artifact_path: Optional[str] = None
    repair_prompt_artifact_path: Optional[str] = None
    gating_decision_artifact_path: Optional[str] = None
    execution_result_artifact_path: Optional[str] = None
    post_execution_decision_artifact_path: Optional[str] = None
    next_step_action_artifact_path: Optional[str] = None
    review_trigger_artifact_path: Optional[str] = None
    review_invocation_result_artifact_path: Optional[str] = None
    review_parsing_handoff_artifact_path: Optional[str] = None
    findings_reentry_artifact_path: Optional[str] = None
    loop_continuation_artifact_path: Optional[str] = None
    blocked_recovery_decision_artifact_path: Optional[str] = None
    retry_decision_artifact_path: Optional[str] = None
    retry_count: int = 0
    retry_budget: int = 2
    created_at: str = ""
    updated_at: str = ""
    parent_work_item_id: Optional[str] = None
    spawned_from_repair_prompt_artifact_path: Optional[str] = None
    spawned_from_findings_artifact_path: Optional[str] = None
    spawned_from_review_artifact_path: Optional[str] = None
    spawned_from_execution_result_artifact_path: Optional[str] = None
    spawned_from_post_execution_decision_artifact_path: Optional[str] = None
    spawned_from_loop_control_decision_artifact_path: Optional[str] = None
    generation_count: int = 0
    repair_loop_generation: int = 0
    child_work_item_ids: list[str] | None = None
    loop_control_decision_artifact_path: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class QueueStep:
    step_id: str
    step_type: str
    input_refs: list[str]
    expected_outputs: list[str]
    metadata: dict[str, Any]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class QueueExecutionPolicy:
    stop_on_block: bool
    allow_warn: bool
    trace_id: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PromptQueueManifest:
    queue_id: str
    created_at: str
    version: str
    steps: list[dict]
    execution_policy: dict

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class QueueState:
    queue_id: str
    queue_status: str
    work_items: list[dict]
    active_work_item_id: Optional[str]
    current_step_index: int
    total_steps: int
    step_results: list[dict]
    created_at: str
    updated_at: str
    last_updated: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReviewAttempt:
    review_attempt_id: str
    work_item_id: str
    provider_requested: str
    provider_used: str
    fallback_used: bool
    fallback_reason: Optional[str]
    attempt_number: int
    outcome_status: str
    started_at: str
    ended_at: str
    review_artifact_path: Optional[str]
    error_message: Optional[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _validate_schema(instance: Any, schema_name: str) -> None:
    validator = Draft202012Validator(load_schema(schema_name), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda e: str(e.path))
    if errors:
        raise QueueValidationError("; ".join(error.message for error in errors))


def _assert_sequential_step_ids(step_ids: list[str]) -> None:
    expected = [f"step-{index:03d}" for index in range(1, len(step_ids) + 1)]
    if step_ids != expected:
        raise QueueValidationError(
            f"Non-deterministic or inconsistent step ordering: expected={expected} actual={step_ids}"
        )


def _assert_deterministic_state_progression(queue_state: dict) -> None:
    step_results = queue_state["step_results"]
    total_steps = queue_state["total_steps"]
    current_step_index = queue_state["current_step_index"]
    queue_status = queue_state["queue_status"]

    if total_steps < 1:
        raise QueueValidationError("total_steps must be >= 1")
    if current_step_index < 0 or current_step_index > total_steps:
        raise QueueValidationError("current_step_index must be between 0 and total_steps")

    step_indexes = [entry["step_index"] for entry in step_results]
    expected_indexes = list(range(len(step_results)))
    if step_indexes != expected_indexes:
        raise QueueValidationError(
            f"Inconsistent step ordering: expected indexes {expected_indexes} but got {step_indexes}"
        )

    step_ids = [entry["step_id"] for entry in step_results]
    _assert_sequential_step_ids(step_ids)

    if queue_status in {QueueStatus.RUNNING.value, QueueStatus.BLOCKED.value} and len(step_results) != current_step_index:
        raise QueueValidationError("running/blocked state requires step_results length to equal current_step_index")

    if queue_status == QueueStatus.PENDING.value:
        if current_step_index != 0 or len(step_results) != 0:
            raise QueueValidationError("pending queue must have index=0 and no step_results")

    if queue_status == QueueStatus.COMPLETED.value:
        if current_step_index != total_steps:
            raise QueueValidationError("completed queue must have current_step_index equal to total_steps")
        if len(step_results) != total_steps:
            raise QueueValidationError("completed queue must include deterministic result for each step")


def validate_queue_manifest_dict(manifest: dict) -> dict:
    _validate_schema(manifest, "prompt_queue_manifest")
    step_ids = [step["step_id"] for step in manifest["steps"]]
    _assert_sequential_step_ids(step_ids)
    return dict(manifest)


def validate_queue_state_dict(queue_state: dict) -> dict:
    _validate_schema(queue_state, "prompt_queue_state")
    _assert_deterministic_state_progression(queue_state)
    normalized = dict(queue_state)
    normalized["last_updated"] = normalized.get("last_updated", normalized.get("updated_at"))
    return normalized


def make_work_item(
    *,
    work_item_id: str,
    prompt_id: str,
    title: str,
    priority: Priority | str,
    risk_level: RiskLevel | str,
    repo: str,
    branch: str,
    scope_paths: list[str],
    parent_work_item_id: Optional[str] = None,
    clock: Clock = utc_now,
) -> dict:
    now = iso_now(clock)
    return WorkItem(
        work_item_id=work_item_id,
        parent_work_item_id=parent_work_item_id,
        prompt_id=prompt_id,
        title=title,
        status=WorkItemStatus.QUEUED.value,
        priority=priority.value if isinstance(priority, Priority) else priority,
        risk_level=risk_level.value if isinstance(risk_level, RiskLevel) else risk_level,
        repo=repo,
        branch=branch,
        scope_paths=scope_paths,
        created_at=now,
        updated_at=now,
        spawned_from_repair_prompt_artifact_path=None,
        spawned_from_findings_artifact_path=None,
        spawned_from_review_artifact_path=None,
        generation_count=0,
        repair_loop_generation=0,
        child_work_item_ids=[],
        gating_decision_artifact_path=None,
        loop_control_decision_artifact_path=None,
        execution_result_artifact_path=None,
        post_execution_decision_artifact_path=None,
        next_step_action_artifact_path=None,
        review_trigger_artifact_path=None,
        review_invocation_result_artifact_path=None,
        review_parsing_handoff_artifact_path=None,
        findings_reentry_artifact_path=None,
        loop_continuation_artifact_path=None,
        blocked_recovery_decision_artifact_path=None,
        retry_decision_artifact_path=None,
        retry_count=0,
        retry_budget=2,
        spawned_from_execution_result_artifact_path=None,
        spawned_from_post_execution_decision_artifact_path=None,
        spawned_from_loop_control_decision_artifact_path=None,
    ).to_dict()


def make_queue_state(*, queue_id: str, work_items: list[dict], clock: Clock = utc_now) -> dict:
    now = iso_now(clock)
    active_work_item_id = work_items[0]["work_item_id"] if work_items else None
    state = QueueState(
        queue_id=queue_id,
        queue_status=QueueStatus.PENDING.value,
        work_items=work_items,
        active_work_item_id=active_work_item_id,
        current_step_index=0,
        total_steps=1,
        step_results=[],
        created_at=now,
        updated_at=now,
        last_updated=now,
    ).to_dict()
    return validate_queue_state_dict(state)
