"""BAX — Budget Authority eXecutor."""

from __future__ import annotations

from typing import Any


_BUDGET_ORDER = {"allow": 0, "warn": 1, "freeze": 2, "block": 3}


def _status(consumed: float, limit: float) -> str:
    if limit <= 0:
        return "block"
    ratio = consumed / limit
    if ratio >= 1:
        return "block"
    if ratio >= 0.9:
        return "freeze"
    if ratio >= 0.75:
        return "warn"
    return "allow"


def compute_cost_budget_status(*, consumption: dict[str, Any], policy: dict[str, Any]) -> tuple[str, list[str]]:
    limits = policy["cost_limits"]
    reasons: list[str] = []
    statuses = []
    for key in ("usd", "tokens", "retries", "wall_clock_minutes"):
        state = _status(float(consumption["cost"][key]), float(limits[key]))
        statuses.append(state)
        if state != "allow":
            reasons.append(f"cost_{key}_{state}")
    merged = max(statuses, key=lambda x: _BUDGET_ORDER[x])
    return merged, reasons


def compute_quality_budget_status(*, consumption: dict[str, Any], policy: dict[str, Any]) -> tuple[str, list[str]]:
    limits = policy["quality_limits"]
    reasons: list[str] = []
    statuses = []
    for key, limit in limits.items():
        state = _status(float(consumption["quality"][key]), float(limit))
        statuses.append(state)
        if state != "allow":
            reasons.append(f"quality_{key}_{state}")
    return max(statuses, key=lambda x: _BUDGET_ORDER[x]), reasons


def compute_risk_budget_status(*, consumption: dict[str, Any], policy: dict[str, Any]) -> tuple[str, list[str]]:
    limits = policy["risk_limits"]
    reasons: list[str] = []
    statuses = []
    for key, limit in limits.items():
        state = _status(float(consumption["risk"][key]), float(limit))
        statuses.append(state)
        if state != "allow":
            reasons.append(f"risk_{key}_{state}")
    return max(statuses, key=lambda x: _BUDGET_ORDER[x]), reasons


def merge_budget_states(*, cost_status: str, quality_status: str, risk_status: str) -> str:
    return max((cost_status, quality_status, risk_status), key=lambda x: _BUDGET_ORDER[x])


def emit_budget_control_decision(*, run_id: str, trace_id: str, status_ref: str, reason_codes: list[str], decision: str) -> dict[str, Any]:
    return {
        "artifact_type": "budget_control_decision",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "decision_id": f"BDEC-{run_id}-{trace_id}",
        "run_id": run_id,
        "trace_id": trace_id,
        "decision": decision,
        "reason_codes": sorted(set(reason_codes)) or ["budget_allow"],
        "status_ref": status_ref,
    }
