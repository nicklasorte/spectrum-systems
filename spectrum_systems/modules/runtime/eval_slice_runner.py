"""Eval slice summarization for regression slices."""

from __future__ import annotations


def summarize_eval_slice(*, eval_id: str, case_results: list[dict[str, object]]) -> dict[str, object]:
    total = len(case_results)
    failed = sum(1 for result in case_results if not bool(result.get("passed", False)))
    return {
        "eval_id": eval_id,
        "total_cases": total,
        "failed_cases": failed,
        "pass_rate": 1.0 if total == 0 else (total - failed) / total,
    }
