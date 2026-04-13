"""Downstream A2A intake guard for arbitration/policy/budget lineage."""

from __future__ import annotations


def enforce_downstream_intake_guard(*, intake: dict[str, bool]) -> tuple[bool, list[str]]:
    required = ["arbitration_lineage", "budget_compatible", "policy_permission"]
    missing = [key for key in required if not bool(intake.get(key, False))]
    return len(missing) == 0, [f"missing:{item}" for item in missing]
