"""CDE long-running task continuation decision.

Produces a deterministic continuation decision when a coding agent requests
to "keep going" or continue after a checkpoint. CDE never executes or enforces;
it emits a decision artifact only.
"""

from __future__ import annotations

from typing import Any, Mapping

_KEEP_GOING_PATTERNS = frozenset({
    "keep_going",
    "keep going",
    "continue until done",
    "finish everything",
    "keep working",
    "dont stop",
    "don't stop",
    "continue indefinitely",
})

_ALLOWED_DECISIONS = frozenset({"continue", "split", "freeze", "block"})


class CDELRTContinuationError(ValueError):
    """Raised when CDE boundary rules for LRT continuation fail closed."""


def decide_lrt_continuation(
    *,
    continuation_phrase: str,
    checkpoint_present: bool,
    stop_after_checkpoint: bool,
    execution_budget: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministic LRT continuation decision. Fail closed on unchecked keep-going requests."""
    phrase_lower = (continuation_phrase or "").lower().strip()
    is_keep_going = phrase_lower in _KEEP_GOING_PATTERNS or any(p in phrase_lower for p in _KEEP_GOING_PATTERNS)

    if is_keep_going and not checkpoint_present:
        return {
            "decision": "block",
            "reason_codes": ["keep_going_without_checkpoint"],
            "block_reason": "continuation request without prior checkpoint is blocked; create checkpoint first",
        }

    if checkpoint_present and stop_after_checkpoint:
        return {
            "decision": "freeze",
            "reason_codes": ["stop_after_checkpoint_enforced"],
            "block_reason": "stop_after_checkpoint=true; agent must halt and report after checkpoint",
        }

    if is_keep_going and checkpoint_present and not stop_after_checkpoint:
        if execution_budget is None:
            return {
                "decision": "split",
                "reason_codes": ["keep_going_requires_split", "no_execution_budget"],
                "block_reason": None,
            }
        return {
            "decision": "continue",
            "reason_codes": ["checkpoint_present", "execution_budget_present"],
            "block_reason": None,
        }

    return {
        "decision": "continue",
        "reason_codes": ["continuation_allowed"],
        "block_reason": None,
    }
