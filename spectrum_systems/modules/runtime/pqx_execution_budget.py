"""PQX execution budget validation.

Provides defaults and validation for the execution_budget contract.
Emits a block signal when a broad task omits, is schema-invalid, or exceeds budget limits.
Does not execute work or make control calls.
"""

from __future__ import annotations

from typing import Any, Mapping

from spectrum_systems.contracts import validate_artifact

EXECUTION_BUDGET_DEFAULTS: dict[str, Any] = {
    "max_files_changed": 3,
    "max_lines_added": 300,
    "max_test_file_lines": 150,
    "max_stage_minutes": 10,
    "checkpoint_required": True,
    "stop_after_checkpoint": True,
}

_BUDGET_FIELDS = frozenset(EXECUTION_BUDGET_DEFAULTS)


class PQXBudgetError(ValueError):
    """Raised when execution proceeds without a valid budget for a broad task."""


def validate_execution_budget(
    budget: Mapping[str, Any] | None,
    *,
    broad_task: bool = False,
) -> dict[str, Any]:
    """Validate execution_budget. Fail closed if broad_task=True and budget missing/invalid/oversized."""
    if budget is None:
        if broad_task:
            raise PQXBudgetError("broad task requires execution_budget; none provided")
        return {"valid": True, "applied_budget": dict(EXECUTION_BUDGET_DEFAULTS), "violations": []}

    if not isinstance(budget, Mapping):
        raise PQXBudgetError(f"execution_budget must be a mapping, got {type(budget).__name__}")

    missing = [f for f in _BUDGET_FIELDS if f not in budget]
    if missing:
        raise PQXBudgetError(f"execution_budget missing required fields: {sorted(missing)}")

    try:
        validate_artifact(dict(budget), "lrt_execution_budget")
    except Exception as exc:
        raise PQXBudgetError(f"execution_budget schema invalid: {exc}") from exc

    violations: list[str] = []
    for key, default in EXECUTION_BUDGET_DEFAULTS.items():
        val = budget.get(key)
        if isinstance(default, int) and isinstance(val, int) and val > default * 10:
            violations.append(f"{key}={val} exceeds 10x default ({default})")

    if violations:
        raise PQXBudgetError(f"execution_budget exceeds limits: {violations}")

    return {
        "valid": True,
        "applied_budget": dict(budget),
        "violations": [],
    }
