"""CAP: Cost and latency budget enforcement.

Artifact families are compared against declared budgets.
Promotion is blocked when actual cost or latency p99 exceeds budget.
"""

from __future__ import annotations

from typing import Dict, Tuple


def check_budget_compliance(
    artifact_family: str,
    actual_cost: float,
    budget_cost: float,
    actual_latency_p99: float,
    budget_latency_ms: float,
) -> Tuple[bool, Dict]:
    """Check whether an artifact family is within its cost and latency budgets.

    Returns (within_budget, report).
    """
    cost_ok = actual_cost <= budget_cost
    latency_ok = actual_latency_p99 <= budget_latency_ms

    report = {
        "artifact_family": artifact_family,
        "cost": {
            "actual": actual_cost,
            "budget": budget_cost,
            "within_budget": cost_ok,
        },
        "latency_p99_ms": {
            "actual": actual_latency_p99,
            "budget": budget_latency_ms,
            "within_budget": latency_ok,
        },
        "overall_within_budget": cost_ok and latency_ok,
    }

    return cost_ok and latency_ok, report
