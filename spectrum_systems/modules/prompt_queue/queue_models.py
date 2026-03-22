"""Models for the governed prompt queue MVP."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Optional


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
    APPROVAL_REQUIRED = "approval_required"
    BLOCKED = "blocked"


class QueueStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    BLOCKED = "blocked"
    COMPLETE = "complete"


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
    review_provider_primary: str = ReviewProvider.CLAUDE.value
    review_provider_actual: Optional[str] = None
    review_attempt_count: int = 0
    review_fallback_used: bool = False
    review_fallback_reason: Optional[str] = None
    findings_artifact_path: Optional[str] = None
    repair_prompt_artifact_path: Optional[str] = None
    gating_decision_artifact_path: Optional[str] = None
    execution_result_artifact_path: Optional[str] = None
    post_execution_decision_artifact_path: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""
    parent_work_item_id: Optional[str] = None
    spawned_from_repair_prompt_artifact_path: Optional[str] = None
    spawned_from_findings_artifact_path: Optional[str] = None
    spawned_from_review_artifact_path: Optional[str] = None
    repair_loop_generation: int = 0
    child_work_item_ids: list[str] | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class QueueState:
    queue_id: str
    queue_status: str
    work_items: list[dict]
    active_work_item_id: Optional[str]
    created_at: str
    updated_at: str

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
        repair_loop_generation=0,
        child_work_item_ids=[],
        gating_decision_artifact_path=None,
        execution_result_artifact_path=None,
        post_execution_decision_artifact_path=None,
    ).to_dict()


def make_queue_state(*, queue_id: str, work_items: list[dict], clock: Clock = utc_now) -> dict:
    now = iso_now(clock)
    active_work_item_id = work_items[0]["work_item_id"] if work_items else None
    return QueueState(
        queue_id=queue_id,
        queue_status=QueueStatus.ACTIVE.value,
        work_items=work_items,
        active_work_item_id=active_work_item_id,
        created_at=now,
        updated_at=now,
    ).to_dict()
