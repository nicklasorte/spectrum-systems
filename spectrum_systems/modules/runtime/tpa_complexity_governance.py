from __future__ import annotations

from copy import deepcopy
from statistics import mean
from typing import Any

from spectrum_systems.contracts import validate_artifact

_DECISION_RANK = {"allow": 0, "warn": 1, "freeze": 2, "block": 3}
_BUDGET_PRIORITY_WEIGHT = {"healthy": 0, "warning": 30, "exceeded": 60}
_TREND_PRIORITY_WEIGHT = {"improving": 0, "stable": 10, "degrading": 30}
_CAMPAIGN_PRIORITY_WEIGHT = {"low": 0, "medium": 10, "high": 20}
_ISSUE_PROPOSAL = {
    "complexity_regression": "tighten_complexity_thresholds",
    "bypass_attempt": "restrict_tpa_optional_paths",
    "simplification_failure": "require_full_tpa_mode",
}


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


def calculate_tpa_priority_score(
    *,
    budget: dict[str, Any] | None,
    trend: dict[str, Any] | None,
    campaign: dict[str, Any] | None,
) -> int:
    if budget is None or trend is None or campaign is None:
        return 0

    budget_status = str(budget.get("budget_status", "healthy"))
    trend_direction = str(trend.get("trend_direction", "stable"))
    campaign_priority = str(campaign.get("priority", "low"))
    reasons = str(campaign.get("reason", ""))

    score = (
        _BUDGET_PRIORITY_WEIGHT.get(budget_status, 0)
        + _TREND_PRIORITY_WEIGHT.get(trend_direction, 0)
        + _CAMPAIGN_PRIORITY_WEIGHT.get(campaign_priority, 0)
    )

    if budget_status == "exceeded":
        score += 5
    if "repeated_complexity_regressions" in reasons:
        score += 5
    if trend_direction == "degrading":
        score += 5
    return min(100, max(0, score))


def classify_system_health_mode(
    *,
    budget: dict[str, Any] | None,
    trend: dict[str, Any] | None,
) -> str:
    if budget is None or trend is None:
        return "critical"

    budget_status = str(budget.get("budget_status", "healthy"))
    trend_direction = str(trend.get("trend_direction", "stable"))
    recommended = strongest_decision(
        "allow",
        str(budget.get("recommended_control_decision", "allow")),
        str(trend.get("recommended_control_decision", "allow")),
    )

    if budget_status == "exceeded" and trend_direction == "degrading":
        return "critical"
    if recommended == "block":
        return "critical"
    if budget_status == "exceeded" or trend_direction == "degrading" or recommended in {"freeze", "warn"}:
        return "degraded"
    return "normal"


def build_control_priority_signal(
    *,
    existing_decision: str,
    budget: dict[str, Any] | None,
    trend: dict[str, Any] | None,
) -> dict[str, Any]:
    mode = classify_system_health_mode(budget=budget, trend=trend)
    effective_decision = enforce_budget_trend_control(existing_decision=existing_decision, budget=budget, trend=trend)
    hardening_prioritized = mode in {"degraded", "critical"}

    if mode == "critical":
        pqx_schedule_mode = "hardening_only"
        promotion_gate = "strict_block_on_regression"
        enforcement_escalation = "critical_enforcement"
    elif mode == "degraded":
        pqx_schedule_mode = "hardening_first"
        promotion_gate = "strict_hardening_before_expansion"
        enforcement_escalation = "degraded_enforcement"
    else:
        pqx_schedule_mode = "balanced"
        promotion_gate = "standard"
        enforcement_escalation = "normal_enforcement"

    return {
        "system_health_mode": mode,
        "effective_control_decision": effective_decision,
        "prioritize_hardening": hardening_prioritized,
        "pqx_schedule_mode": pqx_schedule_mode,
        "promotion_gating_mode": promotion_gate,
        "enforcement_escalation_mode": enforcement_escalation,
    }


def build_tpa_policy_candidate(
    *,
    run_id: str,
    trace_id: str,
    generated_at: str,
    policy_version: str,
    module_scope: str,
    pattern_history: list[dict[str, Any]],
    minimum_recurrence: int = 3,
) -> dict[str, Any] | None:
    repeated: list[dict[str, Any]] = []
    for row in sorted(pattern_history, key=lambda item: (str(item.get("issue_pattern", "")), str(item.get("proposed_change", "")))):
        issue_pattern = str(row.get("issue_pattern", "")).strip()
        occurrence_count = int(row.get("occurrence_count", 0))
        if not issue_pattern or occurrence_count < minimum_recurrence:
            continue
        evidence_refs = sorted({str(ref).strip() for ref in (row.get("evidence_refs") or []) if str(ref).strip()})
        if not evidence_refs:
            continue
        proposed_change = str(row.get("proposed_change") or _ISSUE_PROPOSAL.get(issue_pattern, "tighten_complexity_thresholds"))
        repeated.append(
            {
                "issue_pattern": issue_pattern,
                "occurrence_count": occurrence_count,
                "proposed_change": proposed_change,
                "expected_impact": str(row.get("expected_impact") or "reduce_recurring_tpa_control_failures"),
                "evidence_refs": evidence_refs,
            }
        )

    if not repeated:
        return None

    issue_summary = "_".join(item["issue_pattern"] for item in repeated)
    scope_token = module_scope.replace("/", "_")
    candidate = {
        "artifact_type": "tpa_policy_candidate",
        "schema_version": "1.0.0",
        "candidate_id": f"tpa-policy:{run_id}:{scope_token}:{issue_summary}",
        "run_id": run_id,
        "trace_id": trace_id,
        "generated_at": generated_at,
        "policy_version": policy_version,
        "module_scope": module_scope,
        "issue_pattern": repeated[0]["issue_pattern"] if len(repeated) == 1 else "multi_issue_pattern",
        "proposed_change": repeated[0]["proposed_change"] if len(repeated) == 1 else "bundle_policy_hardening",
        "expected_impact": " ; ".join(item["expected_impact"] for item in repeated),
        "evidence_refs": sorted({ref for item in repeated for ref in item["evidence_refs"]}),
        "review_required": True,
        "lifecycle_state": "proposed",
        "auto_apply": False,
        "detected_patterns": repeated,
    }
    validate_artifact(candidate, "tpa_policy_candidate")
    return candidate


def build_tpa_observability_consumer_record(
    *,
    run_id: str,
    trace_id: str,
    step_id: str,
    generated_at: str,
    observability_summary_ref: str,
    observability_summary: dict[str, Any],
    priority_score: int,
    recommended_control_decision: str,
) -> dict[str, Any]:
    metrics = observability_summary.get("metrics") if isinstance(observability_summary, dict) else {}
    consumed_metrics = [
        "pass2_promotion_rate",
        "simplify_win_rate",
        "complexity_regression_rate",
        "bypass_attempt_count",
    ]
    if not isinstance(metrics, dict):
        raise ValueError("observability_summary.metrics must be an object")
    for key in consumed_metrics[:-1]:
        if key not in metrics:
            raise ValueError(f"observability_summary missing consumed metric: {key}")
    if "bypass_attempt_count" not in observability_summary:
        raise ValueError("observability_summary missing consumed metric: bypass_attempt_count")

    artifact = {
        "artifact_type": "tpa_observability_consumer_record",
        "schema_version": "1.0.0",
        "record_id": f"tpa-observability-consumer:{run_id}:{step_id}",
        "run_id": run_id,
        "trace_id": trace_id,
        "step_id": step_id,
        "generated_at": generated_at,
        "consumer_surface": "control_loop_learning",
        "source_observability_ref": observability_summary_ref,
        "consumed_metrics": consumed_metrics,
        "derived_signals": {
            "priority_score": max(0, min(100, int(priority_score))),
            "recommended_control_decision": str(recommended_control_decision),
        },
    }
    validate_artifact(artifact, "tpa_observability_consumer_record")
    return artifact


def build_complexity_budget_recalibration_record(
    *,
    run_id: str,
    trace_id: str,
    step_id: str,
    generated_at: str,
    complexity_budget_ref: str,
    complexity_trend_ref: str,
    observability_summary_ref: str,
    observed_slice_count: int,
    minimum_slice_count: int = 5,
) -> dict[str, Any]:
    if minimum_slice_count < 1:
        raise ValueError("minimum_slice_count must be >= 1")
    trigger_reasons = ["cadence_due"] if observed_slice_count >= minimum_slice_count else ["insufficient_history"]
    triggered = observed_slice_count >= minimum_slice_count

    artifact = {
        "artifact_type": "complexity_budget_recalibration_record",
        "schema_version": "1.0.0",
        "recalibration_id": f"complexity-recalibration:{run_id}:{step_id}",
        "run_id": run_id,
        "trace_id": trace_id,
        "step_id": step_id,
        "generated_at": generated_at,
        "cadence": {"unit": "slice_interval", "value": minimum_slice_count},
        "trigger": {
            "triggered": triggered,
            "reason_codes": trigger_reasons,
            "observed_slice_count": int(observed_slice_count),
            "minimum_slice_count": int(minimum_slice_count),
        },
        "review_owner": "architecture-review-board",
        "governance_hook_ref": "docs/reviews/2026-04-05-tpa-architecture-review.md",
        "source_refs": {
            "complexity_budget_ref": complexity_budget_ref,
            "complexity_trend_ref": complexity_trend_ref,
            "tpa_observability_summary_ref": observability_summary_ref,
        },
        "decision": "maintain",
        "resulting_update_path": "config/policy/tpa_policy_composition.json",
    }
    validate_artifact(artifact, "complexity_budget_recalibration_record")
    return artifact
