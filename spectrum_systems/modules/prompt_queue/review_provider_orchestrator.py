"""Provider policy and fallback orchestration for governed prompt queue MVP."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from spectrum_systems.modules.prompt_queue.queue_models import (
    FallbackReason,
    ReviewOutcomeStatus,
    ReviewProvider,
    WorkItemStatus,
    iso_now,
    utc_now,
)
from spectrum_systems.modules.prompt_queue.queue_state_machine import transition_work_item


@dataclass(frozen=True)
class ProviderResult:
    success: bool
    failure_reason: Optional[str] = None
    error_message: Optional[str] = None
    review_artifact_path: Optional[str] = None


ProviderRunner = Callable[[dict], ProviderResult]


def _build_attempt(
    *,
    work_item: dict,
    provider_requested: str,
    provider_used: str,
    fallback_used: bool,
    fallback_reason: Optional[str],
    attempt_number: int,
    outcome_status: str,
    started_at: str,
    ended_at: str,
    review_artifact_path: Optional[str],
    error_message: Optional[str],
) -> dict:
    return {
        "review_attempt_id": f"attempt-{work_item['work_item_id']}-{attempt_number}",
        "work_item_id": work_item["work_item_id"],
        "provider_requested": provider_requested,
        "provider_used": provider_used,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "attempt_number": attempt_number,
        "outcome_status": outcome_status,
        "started_at": started_at,
        "ended_at": ended_at,
        "review_artifact_path": review_artifact_path,
        "error_message": error_message,
    }


def run_review_with_fallback(
    work_item: dict,
    *,
    run_claude: ProviderRunner,
    run_codex: ProviderRunner,
    clock: Callable = utc_now,
) -> tuple[dict, list[dict]]:
    attempts: list[dict] = []
    updated = transition_work_item(work_item, WorkItemStatus.REVIEW_QUEUED.value, clock=clock)
    updated = transition_work_item(updated, WorkItemStatus.REVIEW_RUNNING.value, clock=clock)

    attempt_number = int(updated["review_attempt_count"]) + 1
    started = iso_now(clock)
    claude_result = run_claude(updated)
    ended = iso_now(clock)

    if claude_result.success:
        attempts.append(
            _build_attempt(
                work_item=updated,
                provider_requested=ReviewProvider.CLAUDE.value,
                provider_used=ReviewProvider.CLAUDE.value,
                fallback_used=False,
                fallback_reason=None,
                attempt_number=attempt_number,
                outcome_status=ReviewOutcomeStatus.SUCCESS.value,
                started_at=started,
                ended_at=ended,
                review_artifact_path=claude_result.review_artifact_path,
                error_message=None,
            )
        )
        updated["review_provider_actual"] = ReviewProvider.CLAUDE.value
        updated["review_attempt_count"] = attempt_number
        updated = transition_work_item(updated, WorkItemStatus.REVIEW_COMPLETE.value, clock=clock)
        return updated, attempts

    fallback_reason = claude_result.failure_reason
    attempts.append(
        _build_attempt(
            work_item=updated,
            provider_requested=ReviewProvider.CLAUDE.value,
            provider_used=ReviewProvider.CLAUDE.value,
            fallback_used=False,
            fallback_reason=fallback_reason,
            attempt_number=attempt_number,
            outcome_status=ReviewOutcomeStatus.FAILED.value,
            started_at=started,
            ended_at=ended,
            review_artifact_path=None,
            error_message=claude_result.error_message,
        )
    )

    fallback_allowed = fallback_reason in {reason.value for reason in FallbackReason}
    updated["review_attempt_count"] = attempt_number

    if not fallback_allowed:
        updated = transition_work_item(updated, WorkItemStatus.BLOCKED.value, clock=clock)
        updated["review_fallback_used"] = False
        updated["review_fallback_reason"] = fallback_reason
        return updated, attempts

    updated = transition_work_item(updated, WorkItemStatus.REVIEW_PROVIDER_FAILED.value, clock=clock)
    updated = transition_work_item(updated, WorkItemStatus.REVIEW_FALLBACK_RUNNING.value, clock=clock)
    updated["review_fallback_used"] = True
    updated["review_fallback_reason"] = fallback_reason

    attempt_number += 1
    started_fallback = iso_now(clock)
    codex_result = run_codex(updated)
    ended_fallback = iso_now(clock)

    attempts.append(
        _build_attempt(
            work_item=updated,
            provider_requested=ReviewProvider.CLAUDE.value,
            provider_used=ReviewProvider.CODEX.value,
            fallback_used=True,
            fallback_reason=fallback_reason,
            attempt_number=attempt_number,
            outcome_status=ReviewOutcomeStatus.SUCCESS.value if codex_result.success else ReviewOutcomeStatus.FAILED.value,
            started_at=started_fallback,
            ended_at=ended_fallback,
            review_artifact_path=codex_result.review_artifact_path,
            error_message=codex_result.error_message,
        )
    )

    updated["review_attempt_count"] = attempt_number
    updated["review_provider_actual"] = ReviewProvider.CODEX.value

    if codex_result.success:
        updated = transition_work_item(updated, WorkItemStatus.REVIEW_COMPLETE.value, clock=clock)
    else:
        updated = transition_work_item(updated, WorkItemStatus.BLOCKED.value, clock=clock)

    return updated, attempts
