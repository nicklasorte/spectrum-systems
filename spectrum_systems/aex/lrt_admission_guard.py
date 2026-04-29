"""AEX long-running task admission guard.

Detects broad/oversized execution requests and requires a bounded execution_budget
contract before admission proceeds. Does not execute work or make policy decisions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping

from spectrum_systems.contracts import validate_artifact

_BROAD_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"comprehensive\s+test\s+file", "comprehensive_test_file"),
    (r"\bkeep\s+going\b", "keep_going"),
    (r"\bfinish\s+everything\b", "finish_everything"),
    (r"\bwrite\s+all\s+tests\b", "write_all_tests"),
    (r"\blarge\s+refactor\b", "large_refactor"),
    (r"\bentire\s+roadmap\b", "entire_roadmap"),
    (r"\bcontinue\s+until\s+done\b", "continue_until_done"),
)

_BUDGET_REQUIRED_FIELDS = frozenset({
    "max_files_changed",
    "max_lines_added",
    "max_test_file_lines",
    "max_stage_minutes",
    "checkpoint_required",
    "stop_after_checkpoint",
})


@dataclass(frozen=True)
class LRTAdmissionResult:
    admitted: bool
    broad_pattern_detected: bool
    matched_patterns: tuple[str, ...]
    budget_present: bool
    budget_valid: bool
    reason_codes: tuple[str, ...]
    block_reason: str | None


def check_lrt_admission(
    *,
    prompt_text: str,
    execution_budget: Mapping[str, Any] | None,
) -> LRTAdmissionResult:
    """Fail-closed guard: broad prompt without valid execution_budget is blocked."""
    text = (prompt_text or "").lower()
    matched: list[str] = []
    for pattern, label in _BROAD_PATTERNS:
        if re.search(pattern, text):
            matched.append(label)

    broad = bool(matched)

    if not broad:
        return LRTAdmissionResult(
            admitted=True,
            broad_pattern_detected=False,
            matched_patterns=(),
            budget_present=False,
            budget_valid=False,
            reason_codes=("no_broad_pattern",),
            block_reason=None,
        )

    if execution_budget is None:
        return LRTAdmissionResult(
            admitted=False,
            broad_pattern_detected=True,
            matched_patterns=tuple(matched),
            budget_present=False,
            budget_valid=False,
            reason_codes=("broad_pattern_detected", "execution_budget_missing"),
            block_reason="broad task requires execution_budget contract",
        )

    missing = [f for f in _BUDGET_REQUIRED_FIELDS if f not in execution_budget]
    if missing:
        return LRTAdmissionResult(
            admitted=False,
            broad_pattern_detected=True,
            matched_patterns=tuple(matched),
            budget_present=True,
            budget_valid=False,
            reason_codes=("broad_pattern_detected", "execution_budget_incomplete"),
            block_reason=f"execution_budget missing required fields: {sorted(missing)}",
        )

    try:
        validate_artifact(dict(execution_budget), "lrt_execution_budget")
    except Exception as exc:
        return LRTAdmissionResult(
            admitted=False,
            broad_pattern_detected=True,
            matched_patterns=tuple(matched),
            budget_present=True,
            budget_valid=False,
            reason_codes=("broad_pattern_detected", "execution_budget_schema_invalid"),
            block_reason=f"execution_budget schema validation failed: {exc}",
        )

    return LRTAdmissionResult(
        admitted=True,
        broad_pattern_detected=True,
        matched_patterns=tuple(matched),
        budget_present=True,
        budget_valid=True,
        reason_codes=("broad_pattern_detected", "execution_budget_present", "admitted_as_bounded"),
        block_reason=None,
    )
