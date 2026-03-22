"""Pure provider boundary for codex-first live review invocation with bounded fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class InvocationProviderResult:
    success: bool
    output_reference: Optional[str] = None
    failure_reason: Optional[str] = None
    error_message: Optional[str] = None


@dataclass(frozen=True)
class InvocationProviderOutcome:
    provider_requested: str
    provider_used: str
    fallback_used: bool
    fallback_reason: Optional[str]
    invocation_status: str
    output_reference: Optional[str]
    error_summary: Optional[str]


class ReviewInvocationProviderError(ValueError):
    """Raised when provider invocation cannot produce a valid bounded outcome."""


ProviderRunner = Callable[[dict], InvocationProviderResult]
_ALLOWED_FALLBACK_REASONS = {
    "usage_limit",
    "rate_limited",
    "auth_failure",
    "timeout",
    "provider_unavailable",
}


def invoke_review_provider(*, work_item: dict, run_codex: ProviderRunner, run_claude: ProviderRunner) -> InvocationProviderOutcome:
    primary = run_codex(work_item)
    if primary.success:
        return InvocationProviderOutcome(
            provider_requested="codex",
            provider_used="codex",
            fallback_used=False,
            fallback_reason=None,
            invocation_status="success",
            output_reference=primary.output_reference,
            error_summary=None,
        )

    if primary.failure_reason not in _ALLOWED_FALLBACK_REASONS:
        return InvocationProviderOutcome(
            provider_requested="codex",
            provider_used="codex",
            fallback_used=False,
            fallback_reason=None,
            invocation_status="failure",
            output_reference=None,
            error_summary=primary.error_message or "codex invocation failed",
        )

    fallback = run_claude(work_item)
    if fallback.success:
        return InvocationProviderOutcome(
            provider_requested="codex",
            provider_used="claude",
            fallback_used=True,
            fallback_reason=primary.failure_reason,
            invocation_status="success",
            output_reference=fallback.output_reference,
            error_summary=(
                "auth_failure: configuration validation required"
                if primary.failure_reason == "auth_failure"
                else None
            ),
        )

    return InvocationProviderOutcome(
        provider_requested="codex",
        provider_used="claude",
        fallback_used=True,
        fallback_reason=primary.failure_reason,
        invocation_status="failure",
        output_reference=None,
        error_summary=fallback.error_message or "fallback provider invocation failed",
    )
