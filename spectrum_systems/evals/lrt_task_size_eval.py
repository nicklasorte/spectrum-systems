"""EVL deterministic task-size eval for long-running task detection.

Classifies a task as safe_single_slice | requires_split | blocked_until_budgeted.
Missing execution_budget on a risky broad task must not pass (fail closed).
"""

from __future__ import annotations

import re
from typing import Any, Mapping

_BROAD_INDICATORS: tuple[str, ...] = (
    r"comprehensive\s+test\s+file",
    r"\bkeep\s+going\b",
    r"\bfinish\s+everything\b",
    r"\bwrite\s+all\s+tests\b",
    r"\blarge\s+refactor\b",
    r"\bentire\s+roadmap\b",
    r"\bcontinue\s+until\s+done\b",
)

_SPLIT_INDICATORS: tuple[str, ...] = (
    r"\ball\s+\w+\s+files\b",
    r"\bevery\s+module\b",
    r"\bfull\s+implementation\b",
    r"\bcomplete\s+rewrite\b",
)

CLASSIFICATIONS = frozenset({"safe_single_slice", "requires_split", "blocked_until_budgeted"})

_BUDGET_REQUIRED_FIELDS = frozenset({
    "max_files_changed",
    "max_lines_added",
    "max_test_file_lines",
    "max_stage_minutes",
    "checkpoint_required",
    "stop_after_checkpoint",
})


def classify_task_size(
    *,
    prompt_text: str,
    execution_budget: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Classify task size. Fail closed: broad task without budget → blocked_until_budgeted."""
    text = (prompt_text or "").lower()

    broad = any(re.search(p, text) for p in _BROAD_INDICATORS)
    needs_split = any(re.search(p, text) for p in _SPLIT_INDICATORS)

    if not broad and not needs_split:
        return {
            "classification": "safe_single_slice",
            "reason_codes": ["no_broad_indicators"],
            "budget_required": False,
        }

    if needs_split and not broad:
        return {
            "classification": "requires_split",
            "reason_codes": ["split_indicator_detected"],
            "budget_required": True,
        }

    budget_present = execution_budget is not None
    if budget_present:
        if not isinstance(execution_budget, Mapping):
            return {
                "classification": "blocked_until_budgeted",
                "reason_codes": ["broad_task_detected", "execution_budget_not_a_mapping"],
                "budget_required": True,
            }
        missing = [f for f in _BUDGET_REQUIRED_FIELDS if f not in execution_budget]
        if missing:
            return {
                "classification": "blocked_until_budgeted",
                "reason_codes": ["broad_task_detected", "execution_budget_incomplete"],
                "budget_required": True,
                "missing_budget_fields": sorted(missing),
            }
        return {
            "classification": "requires_split",
            "reason_codes": ["broad_task_detected", "execution_budget_present"],
            "budget_required": True,
        }

    return {
        "classification": "blocked_until_budgeted",
        "reason_codes": ["broad_task_detected", "execution_budget_missing"],
        "budget_required": True,
    }
