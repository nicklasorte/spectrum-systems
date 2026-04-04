from __future__ import annotations

from copy import deepcopy
from statistics import mean
from typing import Any

from spectrum_systems.contracts import validate_artifact

_DECISION_RANK = {"allow": 0, "warn": 1, "freeze": 2, "block": 3}


def _complexity_score(signals: dict[str, int]) -> int:
    return (
        (signals["lines_added"] - signals["lines_removed"])
        + signals["helpers_added_count"] * 2
        + signals["functions_added_count"] * 2
        + signals["abstraction_added_count"] * 3
        + signals["public_surface_delta_count"] * 3
        + signals["approximate_max_nesting_delta"] * 2
        + signals["approximate_branching_delta"] * 2
        - signals["helpers_removed_count"] * 2
        - signals["functions_removed_count"] * 2
        - signals["abstraction_removed_count"] * 3
        - signals["wrappers_collapsed_count"] * 2
        - signals["deletions_count"] * 2
    )


def _ranked(module: str, score: float) -> dict[str, Any]:
    return {"module": module, "score": round(float(score), 6)}


def strongest_decision(*decisions: str) -> str:
    known = [d for d in decisions if d in _DECISION_RANK]
    if not known:
        return "allow"
    return max(known, key=lambda d: _DECISION_RANK[d])


def build_complexity_budget(
    *,
    run_id: str,
    trace_id: str,
    step_id: str,
    module_or_path: str,
    build_signals: dict[str, int],
    simplify_signals: dict[str, int],
    last_updated: str,
    historical_scores: list[int] | None = None,
    allowed_growth_delta: int = 6,
) -> dict[str, Any]:
    history = list(historical_scores or [])
    current_complexity = _complexity_score(simplify_signals)
    baseline_complexity = history[-1] if history else _complexity_score(build_signals)
    growth = current_complexity - baseline_complexity
    sustained_increase_count = sum(1 for score in history[-3:] if score > baseline_complexity)
    burn_rate = 0.0 if allowed_growth_delta == 0 else max(0.0, growth / float(allowed_growth_delta))

    if growth <= allowed_growth_delta:
        budget_status = "healthy"
        recommended = "allow"
    elif growth <= allowed_growth_delta * 2 and sustained_increase_count < 2:
        budget_status = "warning"
        recommended = "warn"
    else:
        budget_status = "exceeded"
        recommended = "freeze" if (growth <= allowed_growth_delta * 3 and sustained_increase_count < 3) else "block"

    artifact = {
        "artifact_type": "complexity_budget",
        "schema_version": "1.0.0",
        "run_id": run_id,
        "trace_id": trace_id,
        "step_id": step_id,
        "module_or_path": module_or_path,
        "baseline_complexity": baseline_complexity,
        "current_complexity": current_complexity,
        "allowed_growth_delta": allowed_growth_delta,
        "budget_status": budget_status,
        "burn_rate": round(burn_rate, 6),
        "last_updated": last_updated,
        "sustained_increase_count": sustained_increase_count,
        "recommended_control_decision": recommended,
        "evidence_refs": [
            f"tpa_slice_artifact:{run_id}:{step_id}-B",
            f"tpa_slice_artifact:{run_id}:{step_id}-S",
        ],
    }
    validate_artifact(artifact, "complexity_budget")
    return artifact


def build_complexity_trend(
    *,
    run_id: str,
    trace_id: str,
    step_id: str,
    module: str,
    artifact_type_scope: str,
    slice_family: str,
    points: list[dict[str, Any]],
) -> dict[str, Any]:
    if not points:
        raise ValueError("complexity trend requires at least one point")
    ordered = [deepcopy(point) for point in points]
    deltas = [int(point["complexity_delta"]) for point in ordered]
    simplify_values = [float(point["simplify_effectiveness"]) for point in ordered]
    deletion_values = [int(point["deletions_count"]) for point in ordered]
    abstraction_values = [int(point["abstraction_growth"]) for point in ordered]

    avg_delta = mean(deltas)
    if avg_delta > 1.0:
        trend_direction = "degrading"
    elif avg_delta < -1.0:
        trend_direction = "improving"
    else:
        trend_direction = "stable"

    volatility = mean(abs(delta - avg_delta) for delta in deltas)
    regression_points = [point["step_id"] for point in ordered if int(point["complexity_delta"]) > 0]
    stability_score = max(0.0, 1.0 - min(1.0, volatility / 10.0))
    simplify_effectiveness = mean(simplify_values)
    deletion_rate = mean(deletion_values)
    abstraction_growth = mean(abstraction_values)

    if trend_direction == "degrading" and volatility >= 2.0:
        recommended = "freeze"
    elif trend_direction == "degrading":
        recommended = "warn"
    elif trend_direction == "stable" and volatility >= 4.0:
        recommended = "warn"
    else:
        recommended = "allow"

    artifact = {
        "artifact_type": "complexity_trend",
        "schema_version": "1.0.0",
        "run_id": run_id,
        "trace_id": trace_id,
        "step_id": step_id,
        "module": module,
        "artifact_type_scope": artifact_type_scope,
        "slice_family": slice_family,
        "points": ordered,
        "trend_direction": trend_direction,
        "volatility": round(volatility, 6),
        "regression_points": regression_points,
        "stability_score": round(stability_score, 6),
        "simplify_effectiveness": round(simplify_effectiveness, 6),
        "deletion_rate": round(deletion_rate, 6),
        "abstraction_growth": round(abstraction_growth, 6),
        "query_views": {
            "top_degrading_modules": [_ranked(module, avg_delta if avg_delta > 0 else 0.0)],
            "most_improved_modules": [_ranked(module, -avg_delta if avg_delta < 0 else 0.0)],
            "most_volatile_modules": [_ranked(module, volatility)],
        },
        "recommended_control_decision": recommended,
    }
    validate_artifact(artifact, "complexity_trend")
    return artifact


def build_simplification_campaign(
    *,
    run_id: str,
    trace_id: str,
    step_id: str,
    target_module: str,
    trend: dict[str, Any],
    budget: dict[str, Any],
) -> dict[str, Any]:
    repeated_regressions = len(trend.get("regression_points", [])) >= 2
    low_simplify_success = float(trend.get("simplify_effectiveness", 0.0)) < 0
    high_abstraction_growth = float(trend.get("abstraction_growth", 0.0)) > 1

    reasons: list[str] = []
    if repeated_regressions:
        reasons.append("repeated_complexity_regressions")
    if low_simplify_success:
        reasons.append("low_simplify_success_rate")
    if high_abstraction_growth:
        reasons.append("high_abstraction_growth")
    if budget.get("budget_status") == "exceeded":
        reasons.append("complexity_budget_exceeded")

    if not reasons:
        reasons.append("preventative_cleanup")

    if "complexity_budget_exceeded" in reasons:
        action = "refactor"
        priority = "high"
    elif "high_abstraction_growth" in reasons:
        action = "delete"
        priority = "high"
    elif "repeated_complexity_regressions" in reasons:
        action = "simplify"
        priority = "medium"
    else:
        action = "simplify"
        priority = "low"

    artifact = {
        "artifact_type": "tpa_simplification_campaign",
        "schema_version": "1.0.0",
        "run_id": run_id,
        "trace_id": trace_id,
        "step_id": step_id,
        "target_module": target_module,
        "reason": ",".join(reasons),
        "recommended_action": action,
        "priority": priority,
        "evidence_refs": [
            f"complexity_budget:{budget['run_id']}:{budget['step_id']}",
            f"complexity_trend:{trend['run_id']}:{trend['step_id']}",
        ],
        "pqx_cleanup_ready": True,
    }
    validate_artifact(artifact, "tpa_simplification_campaign")
    return artifact


def enforce_budget_trend_control(
    *,
    existing_decision: str,
    budget: dict[str, Any] | None,
    trend: dict[str, Any] | None,
) -> str:
    if budget is None or trend is None:
        return "block"
    return strongest_decision(
        existing_decision,
        str(budget.get("recommended_control_decision", "allow")),
        str(trend.get("recommended_control_decision", "allow")),
    )
