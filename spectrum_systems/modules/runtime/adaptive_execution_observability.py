"""Deterministic adaptive execution observability + guardrail trend reporting (BATCH-X1)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class AdaptiveExecutionObservabilityError(ValueError):
    """Raised when adaptive execution observability artifacts cannot be safely derived."""


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_schema(instance: dict[str, Any], schema_name: str) -> None:
    validator = Draft202012Validator(load_schema(schema_name), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise AdaptiveExecutionObservabilityError(f"{schema_name} validation failed: {details}")


def _to_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _round4(value: float) -> float:
    return round(value, 4)


def _safe_rate(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return _round4(max(0.0, min(1.0, numerator / denominator)))


def _distribution_from_counts(counts: dict[str, int], total: int) -> dict[str, float]:
    return {key: _safe_rate(float(counts[key]), float(total)) for key in sorted(counts)}


def _trend_direction(values: list[float], *, lower_is_better: bool = False) -> str:
    if len(values) < 2:
        return "stable"
    midpoint = len(values) // 2
    first_window = values[:midpoint] or values[:1]
    second_window = values[midpoint:] or values[-1:]
    first_avg = sum(first_window) / len(first_window)
    second_avg = sum(second_window) / len(second_window)
    delta = second_avg - first_avg
    if abs(delta) < 0.01:
        return "stable"
    improving = delta < 0 if lower_is_better else delta > 0
    return "improving" if improving else "degrading"


def _resolve_created_at(sorted_runs: list[dict[str, Any]], created_at: str | None) -> str:
    if created_at:
        return created_at
    timestamps = [str(run.get("executed_at") or "").strip() for run in sorted_runs if str(run.get("executed_at") or "").strip()]
    if timestamps:
        return sorted(timestamps)[-1]
    return "1970-01-01T00:00:00Z"


def build_adaptive_execution_observability(
    run_results: list[dict[str, Any]],
    *,
    trace_id: str,
    source_refs: list[str] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Aggregate bounded multi-run adaptive execution metrics deterministically."""
    if not isinstance(trace_id, str) or not trace_id.strip():
        raise AdaptiveExecutionObservabilityError("trace_id is required")

    normalized_runs = [dict(item) for item in run_results if isinstance(item, dict)]
    sorted_runs = sorted(normalized_runs, key=lambda run: str(run.get("run_id") or ""))
    runs_observed = len(sorted_runs)

    resolved_caps: list[float] = []
    attempted_batches: list[float] = []
    useful_batches: list[float] = []
    early_stops = 0

    stop_reason_counts: dict[str, int] = {}
    continuation_counts: dict[str, int] = {"continue": 0, "stop": 0}
    risk_level_counts: dict[str, int] = {"low": 0, "medium": 0, "high": 0}

    replay_integrity_pass = 0
    determinism_integrity_pass = 0
    boundary_violations = 0

    for run in sorted_runs:
        resolved_caps.append(_to_float(run.get("resolved_max_batches_per_run"), default=0.0))

        efficiency = run.get("execution_efficiency_report") if isinstance(run.get("execution_efficiency_report"), dict) else {}
        attempted = _to_float(efficiency.get("batches_executed_per_run"), default=0.0)
        useful = _to_float(efficiency.get("useful_batches"), default=_to_float(run.get("batches_executed_count"), default=0.0))
        attempted_batches.append(attempted)
        useful_batches.append(useful)
        if int(efficiency.get("early_stops") or 0) > 0:
            early_stops += 1

        stop_reason = str(run.get("stop_reason") or "unknown_stop_reason")
        stop_reason_counts[stop_reason] = stop_reason_counts.get(stop_reason, 0) + 1

        sequence = run.get("continuation_decision_sequence")
        if isinstance(sequence, list):
            for item in sequence:
                if not isinstance(item, dict):
                    continue
                decision = str(item.get("decision") or "")
                if decision in continuation_counts:
                    continuation_counts[decision] += 1

        adaptive_factors = efficiency.get("adaptive_factors") if isinstance(efficiency.get("adaptive_factors"), dict) else {}
        risk_level = str(adaptive_factors.get("risk_level") or "medium").lower()
        if risk_level not in risk_level_counts:
            risk_level = "medium"
        risk_level_counts[risk_level] += 1

        replay_ok = bool(run.get("loop_validation_refs")) and stop_reason != "replay_not_ready"
        replay_integrity_pass += 1 if replay_ok else 0

        source_refs_for_run = run.get("source_refs") if isinstance(run.get("source_refs"), list) else []
        is_deterministic = source_refs_for_run == sorted(set(str(item) for item in source_refs_for_run))
        determinism_integrity_pass += 1 if is_deterministic else 0

        if stop_reason in {"authorization_block", "authorization_freeze", "hard_gate_stop"}:
            pass
        elif stop_reason in {"replay_not_ready", "missing_required_signal", "contract_precondition_failed"}:
            boundary_violations += 1

    average_resolved_max_batches_per_run = _round4(sum(resolved_caps) / runs_observed) if runs_observed else 0.0
    average_batches_executed_per_run = _round4(sum(attempted_batches) / runs_observed) if runs_observed else 0.0
    average_useful_batches_per_run = _round4(sum(useful_batches) / runs_observed) if runs_observed else 0.0

    early_stop_rate = _safe_rate(float(early_stops), float(runs_observed))
    stop_reason_distribution = _distribution_from_counts(stop_reason_counts, runs_observed)

    total_continuation_decisions = continuation_counts["continue"] + continuation_counts["stop"]
    continuation_decision_distribution = _distribution_from_counts(continuation_counts, total_continuation_decisions)
    risk_level_distribution = _distribution_from_counts(risk_level_counts, runs_observed)

    replay_integrity_rate = _safe_rate(float(replay_integrity_pass), float(runs_observed))
    determinism_integrity_rate = _safe_rate(float(determinism_integrity_pass), float(runs_observed))

    if boundary_violations > 0:
        control_boundary_integrity_status = "violated"
    elif early_stop_rate > 0.5:
        control_boundary_integrity_status = "watch"
    else:
        control_boundary_integrity_status = "bounded"

    normalized_source_refs = sorted(
        set((source_refs or []) + [f"roadmap_multi_batch_run_result:{str(run.get('run_id') or 'unknown')}" for run in sorted_runs])
    )

    created_timestamp = _resolve_created_at(sorted_runs, created_at)
    seed = {
        "trace_id": trace_id.strip(),
        "runs": [str(run.get("run_id") or "") for run in sorted_runs],
        "created_at": created_timestamp,
    }
    observability = {
        "observability_id": f"AEO-{_hash(seed)[:12].upper()}",
        "schema_version": "1.0.0",
        "created_at": created_timestamp,
        "trace_id": trace_id.strip(),
        "source_refs": normalized_source_refs,
        "runs_observed": runs_observed,
        "average_resolved_max_batches_per_run": average_resolved_max_batches_per_run,
        "average_batches_executed_per_run": average_batches_executed_per_run,
        "average_useful_batches_per_run": average_useful_batches_per_run,
        "early_stop_rate": early_stop_rate,
        "stop_reason_distribution": stop_reason_distribution,
        "continuation_decision_distribution": continuation_decision_distribution,
        "risk_level_distribution": risk_level_distribution,
        "replay_integrity_rate": replay_integrity_rate,
        "determinism_integrity_rate": determinism_integrity_rate,
        "control_boundary_integrity_status": control_boundary_integrity_status,
    }
    _validate_schema(observability, "adaptive_execution_observability")
    return observability


def build_adaptive_execution_trend_report(
    run_results: list[dict[str, Any]],
    *,
    observability: dict[str, Any],
    trace_id: str,
    created_at: str | None = None,
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Build deterministic adaptive execution trend report with machine-readable guardrails."""
    if not isinstance(observability, dict):
        raise AdaptiveExecutionObservabilityError("observability artifact is required")

    _validate_schema(observability, "adaptive_execution_observability")

    normalized_runs = [dict(item) for item in run_results if isinstance(item, dict)]
    sorted_runs = sorted(normalized_runs, key=lambda run: str(run.get("run_id") or ""))
    runs_observed = len(sorted_runs)

    policy_thresholds = {
        "max_early_stop_rate": 0.6,
        "min_useful_batches_per_run": 1.0,
        "max_risk_stop_share": 0.4,
        "max_cap_without_useful_gap": 1.5,
        "min_replay_integrity_rate": 0.95,
        "max_unsafe_continuation_rate": 0.85,
    }
    if isinstance(thresholds, dict):
        for key, value in thresholds.items():
            if key in policy_thresholds and isinstance(value, (int, float)):
                policy_thresholds[key] = float(value)

    risk_stop_codes = {"risk_accumulation_threshold_exceeded", "diminishing_returns_detected", "repeated_failure_pattern"}
    risk_stop_count = sum(1 for run in sorted_runs if str(run.get("stop_reason") or "") in risk_stop_codes)

    stop_rate_series: list[float] = []
    useful_series: list[float] = []
    for run in sorted_runs:
        efficiency = run.get("execution_efficiency_report") if isinstance(run.get("execution_efficiency_report"), dict) else {}
        stop_rate_series.append(1.0 if int(efficiency.get("early_stops") or 0) > 0 else 0.0)
        useful_series.append(_to_float(efficiency.get("useful_batches"), default=_to_float(run.get("batches_executed_count"), default=0.0)))

    continuation_distribution = observability.get("continuation_decision_distribution") if isinstance(observability.get("continuation_decision_distribution"), dict) else {}
    continue_rate = _to_float(continuation_distribution.get("continue"), default=0.0)

    checks = [
        {
            "check_id": "early_stop_rate_high",
            "status": "triggered"
            if _to_float(observability.get("early_stop_rate")) > policy_thresholds["max_early_stop_rate"]
            else "ok",
            "threshold": policy_thresholds["max_early_stop_rate"],
            "observed": _to_float(observability.get("early_stop_rate")),
            "direction": "lower_is_better",
            "message": "Early-stop frequency should remain bounded to preserve throughput and trust.",
        },
        {
            "check_id": "useful_batches_stagnant_or_degrading",
            "status": "triggered"
            if (
                _to_float(observability.get("average_useful_batches_per_run")) < policy_thresholds["min_useful_batches_per_run"]
                or _trend_direction(useful_series) == "degrading"
            )
            else "ok",
            "threshold": policy_thresholds["min_useful_batches_per_run"],
            "observed": _to_float(observability.get("average_useful_batches_per_run")),
            "direction": "higher_is_better",
            "message": "Useful batch output should improve or hold steady as caps adapt.",
        },
        {
            "check_id": "risk_triggered_stops_rising",
            "status": "triggered"
            if _safe_rate(float(risk_stop_count), float(max(runs_observed, 1))) > policy_thresholds["max_risk_stop_share"]
            else "ok",
            "threshold": policy_thresholds["max_risk_stop_share"],
            "observed": _safe_rate(float(risk_stop_count), float(max(runs_observed, 1))),
            "direction": "lower_is_better",
            "message": "Risk-triggered stops should not dominate bounded adaptive execution.",
        },
        {
            "check_id": "resolved_cap_without_useful_work",
            "status": "triggered"
            if (
                _to_float(observability.get("average_resolved_max_batches_per_run"))
                - _to_float(observability.get("average_useful_batches_per_run"))
            )
            > policy_thresholds["max_cap_without_useful_gap"]
            else "ok",
            "threshold": policy_thresholds["max_cap_without_useful_gap"],
            "observed": _round4(
                _to_float(observability.get("average_resolved_max_batches_per_run"))
                - _to_float(observability.get("average_useful_batches_per_run"))
            ),
            "direction": "lower_is_better",
            "message": "Cap increases must correspond to useful work, not speculative churn.",
        },
        {
            "check_id": "replay_integrity_degradation",
            "status": "triggered"
            if _to_float(observability.get("replay_integrity_rate")) < policy_thresholds["min_replay_integrity_rate"]
            else "ok",
            "threshold": policy_thresholds["min_replay_integrity_rate"],
            "observed": _to_float(observability.get("replay_integrity_rate")),
            "direction": "higher_is_better",
            "message": "Replay integrity must remain high for safe deterministic tuning.",
        },
        {
            "check_id": "unsafe_continuation_aggressiveness",
            "status": "triggered" if continue_rate > policy_thresholds["max_unsafe_continuation_rate"] else "ok",
            "threshold": policy_thresholds["max_unsafe_continuation_rate"],
            "observed": continue_rate,
            "direction": "lower_is_better",
            "message": "Continuation rate should stay bounded by risk-aware policy guardrails.",
        },
    ]

    triggered = sorted([check["check_id"] for check in checks if check["status"] == "triggered"])
    guardrail_status = "alert" if triggered else "within_guardrails"

    early_stop_trend = _trend_direction(stop_rate_series, lower_is_better=True)
    useful_work_trend = _trend_direction(useful_series)

    if guardrail_status == "alert":
        autonomy_effectiveness = "needs_tuning"
    elif useful_work_trend == "improving" and early_stop_trend in {"stable", "improving"}:
        autonomy_effectiveness = "improving"
    else:
        autonomy_effectiveness = "stable"

    if observability.get("control_boundary_integrity_status") == "violated":
        safety_trend = "riskier"
    elif guardrail_status == "alert":
        safety_trend = "watch"
    else:
        safety_trend = "safer"

    created_timestamp = created_at or str(observability.get("created_at") or _utc_now())
    seed = {
        "trace_id": trace_id,
        "runs": [str(run.get("run_id") or "") for run in sorted_runs],
        "created_at": created_timestamp,
        "guardrail_status": guardrail_status,
    }
    report = {
        "trend_report_id": f"AET-{_hash(seed)[:12].upper()}",
        "schema_version": "1.0.0",
        "created_at": created_timestamp,
        "trace_id": trace_id,
        "observability_ref": f"adaptive_execution_observability:{observability['observability_id']}",
        "runs_observed": runs_observed,
        "autonomy_effectiveness": autonomy_effectiveness,
        "safety_trend": safety_trend,
        "guardrail_status": guardrail_status,
        "guardrail_checks": checks,
        "trend_signals": {
            "early_stop_rate_trend": early_stop_trend,
            "useful_batches_per_run_trend": useful_work_trend,
            "risk_stop_share": _safe_rate(float(risk_stop_count), float(max(runs_observed, 1))),
            "resolved_cap_efficiency_gap": _round4(
                _to_float(observability.get("average_resolved_max_batches_per_run"))
                - _to_float(observability.get("average_useful_batches_per_run"))
            ),
        },
        "tuning_warranted": bool(triggered),
        "watch_next": triggered
        if triggered
        else ["monitor_guardrail_drift", "confirm_cap_policy_continues_to_match_useful_output"],
        "source_refs": sorted(
            set(
                list(observability.get("source_refs", []))
                + [
                    f"adaptive_execution_observability:{observability['observability_id']}",
                ]
            )
        ),
    }
    _validate_schema(report, "adaptive_execution_trend_report")
    return report


def _dominant_distribution_entries(distribution: dict[str, Any], *, limit: int = 3) -> list[dict[str, Any]]:
    normalized: list[tuple[str, float]] = []
    for key, value in distribution.items():
        if isinstance(key, str):
            normalized.append((key, _to_float(value)))
    ranked = sorted(normalized, key=lambda item: (-item[1], item[0]))
    return [{"name": item[0], "share": _round4(item[1])} for item in ranked[:limit]]


def build_adaptive_execution_policy_review(
    run_results: list[dict[str, Any]],
    *,
    observability: dict[str, Any],
    trend_report: dict[str, Any],
    trace_id: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build deterministic evidence-backed policy review and prior-vs-tuned comparison."""
    if not isinstance(trace_id, str) or not trace_id.strip():
        raise AdaptiveExecutionObservabilityError("trace_id is required")
    _validate_schema(observability, "adaptive_execution_observability")
    _validate_schema(trend_report, "adaptive_execution_trend_report")

    sorted_runs = sorted(
        [dict(item) for item in run_results if isinstance(item, dict)],
        key=lambda run: str(run.get("run_id") or ""),
    )
    stop_distribution = dict(observability.get("stop_reason_distribution") or {})
    continuation_distribution = dict(observability.get("continuation_decision_distribution") or {})
    risk_distribution = dict(observability.get("risk_level_distribution") or {})
    guardrail_checks = trend_report.get("guardrail_checks")
    guardrails = guardrail_checks if isinstance(guardrail_checks, list) else []

    dominant_stop_patterns = _dominant_distribution_entries(stop_distribution, limit=4)
    dominant_failure_modes = [
        entry
        for entry in dominant_stop_patterns
        if entry["name"]
        in {
            "risk_accumulation_threshold_exceeded",
            "repeated_failure_pattern",
            "diminishing_returns_detected",
            "execution_blocked",
            "replay_not_ready",
            "unresolved_blocker_persists",
        }
    ]
    if not dominant_failure_modes:
        dominant_failure_modes = [{"name": "none_dominant", "share": 0.0}]

    early_stop_rate = _to_float(observability.get("early_stop_rate"))
    useful_per_run = _to_float(observability.get("average_useful_batches_per_run"))
    resolved_cap = _to_float(observability.get("average_resolved_max_batches_per_run"))
    cap_gap = _round4(max(0.0, resolved_cap - useful_per_run))
    continue_rate = _to_float(continuation_distribution.get("continue"))
    high_risk_share = _to_float(risk_distribution.get("high"))
    low_risk_share = _to_float(risk_distribution.get("low"))
    replay_integrity_rate = _to_float(observability.get("replay_integrity_rate"))

    triggered_guardrails = sorted(
        str(check.get("check_id"))
        for check in guardrails
        if isinstance(check, dict) and str(check.get("status")) == "triggered"
    )

    recommended_policy_changes: list[dict[str, Any]] = []
    tuned_policy = {
        "risk_accumulation_stop_threshold": 6,
        "consecutive_non_progress_stop_threshold": 2,
        "repeated_failure_reason_stop_threshold": 2,
        "unresolved_blocker_stop_threshold": 2,
        "replay_integrity_stop_threshold": 0.95,
        "enable_low_risk_bonus_batch": False,
    }

    if early_stop_rate >= 0.5 or "risk_triggered_stops_rising" in triggered_guardrails:
        tuned_policy["risk_accumulation_stop_threshold"] = 5
        recommended_policy_changes.append(
            {
                "change_id": "tighten_risk_accumulation_cap",
                "rule_target": "risk_accumulation_stop_threshold",
                "from_value": 6,
                "to_value": 5,
                "reason": "High early-stop/risk-triggered stop share indicates accumulating risk should halt continuation earlier.",
            }
        )

    if cap_gap >= 1.0 or "resolved_cap_without_useful_work" in triggered_guardrails:
        tuned_policy["consecutive_non_progress_stop_threshold"] = 1
        recommended_policy_changes.append(
            {
                "change_id": "stop_earlier_on_non_progress",
                "rule_target": "consecutive_non_progress_stop_threshold",
                "from_value": 2,
                "to_value": 1,
                "reason": "Large useful-work vs cap gap indicates unproductive continuation; stop after one non-progress event.",
            }
        )

    if replay_integrity_rate < 1.0 or "replay_integrity_degradation" in triggered_guardrails:
        tuned_policy["repeated_failure_reason_stop_threshold"] = 1
        recommended_policy_changes.append(
            {
                "change_id": "tighten_after_replay_drift",
                "rule_target": "repeated_failure_reason_stop_threshold",
                "from_value": 2,
                "to_value": 1,
                "reason": "Replay integrity drift requires stricter repeated-failure continuation limits to preserve determinism.",
            }
        )

    if useful_per_run >= 1.6 and low_risk_share >= 0.4 and high_risk_share <= 0.25 and early_stop_rate <= 0.4:
        tuned_policy["enable_low_risk_bonus_batch"] = True
        recommended_policy_changes.append(
            {
                "change_id": "allow_one_bonus_batch_when_low_risk",
                "rule_target": "enable_low_risk_bonus_batch",
                "from_value": False,
                "to_value": True,
                "reason": "Useful throughput is strong and risk remains low, so one bounded extra attempt is justified.",
            }
        )

    rejected_policy_changes = [
        {
            "change_id": "raise_global_max_cap_to_6",
            "status": "rejected",
            "reason": "conflicts_with_fail_closed_posture",
        },
        {
            "change_id": "probabilistic_continuation_exploration",
            "status": "rejected",
            "reason": "non_deterministic_not_allowed",
        },
        {
            "change_id": "disable_risk_stop_reasons",
            "status": "rejected",
            "reason": "weakens_authority_boundaries",
        },
    ]

    baseline_unproductive = _round4(_safe_rate(max(0.0, resolved_cap - useful_per_run), max(resolved_cap, 1.0)))
    tuned_unproductive = baseline_unproductive
    tuned_useful = useful_per_run
    tuned_risk_exposure = _round4(high_risk_share + (continue_rate * 0.5))
    if tuned_policy["consecutive_non_progress_stop_threshold"] == 1:
        tuned_unproductive = _round4(max(0.0, tuned_unproductive - 0.15))
        tuned_risk_exposure = _round4(max(0.0, tuned_risk_exposure - 0.06))
    if tuned_policy["risk_accumulation_stop_threshold"] == 5:
        tuned_risk_exposure = _round4(max(0.0, tuned_risk_exposure - 0.08))
    if tuned_policy["enable_low_risk_bonus_batch"]:
        tuned_useful = _round4(tuned_useful + 0.2)
        tuned_unproductive = _round4(max(0.0, tuned_unproductive - 0.03))

    operator_tuning_signals = [
        (
            "policy_tuned_due_to_high_early_stop_rate"
            if early_stop_rate >= 0.5
            else "policy_hold_or_partial_tune_based_on_early_stop_rate"
        ),
        (
            "cap_held_conservative_due_to_risk_triggers"
            if "risk_triggered_stops_rising" in triggered_guardrails
            else "cap_expansion_not_auto_enabled_without_low_risk_evidence"
        ),
        (
            "continuation_stricter_due_to_useful_work_gap"
            if cap_gap >= 1.0
            else "continuation_strictness_unchanged_for_useful_work_gap"
        ),
    ]

    created_timestamp = created_at or _resolve_created_at(sorted_runs, None)
    seed = {
        "trace_id": trace_id.strip(),
        "created_at": created_timestamp,
        "observability_id": observability["observability_id"],
        "trend_report_id": trend_report["trend_report_id"],
        "recommended_count": len(recommended_policy_changes),
    }
    review = {
        "review_id": f"AEPR-{_hash(seed)[:12].upper()}",
        "schema_version": "1.0.0",
        "created_at": created_timestamp,
        "trace_id": trace_id.strip(),
        "policy_inputs_reviewed": {
            "runs_observed": int(observability.get("runs_observed") or 0),
            "observability_ref": f"adaptive_execution_observability:{observability['observability_id']}",
            "trend_report_ref": f"adaptive_execution_trend_report:{trend_report['trend_report_id']}",
            "latest_run_ref": f"roadmap_multi_batch_run_result:{str(sorted_runs[-1].get('run_id') if sorted_runs else 'none')}",
        },
        "signals_used": {
            "early_stop_rate": early_stop_rate,
            "average_useful_batches_per_run": useful_per_run,
            "average_resolved_max_batches_per_run": resolved_cap,
            "useful_work_vs_cap_gap": cap_gap,
            "risk_level_distribution": risk_distribution,
            "continuation_decision_distribution": continuation_distribution,
            "dominant_guardrail_triggers": triggered_guardrails,
        },
        "dominant_failure_modes": dominant_failure_modes,
        "dominant_stop_patterns": dominant_stop_patterns,
        "recommended_policy_changes": recommended_policy_changes,
        "rejected_policy_changes": rejected_policy_changes,
        "policy_comparison": {
            "prior_policy": {
                "risk_accumulation_stop_threshold": 6,
                "consecutive_non_progress_stop_threshold": 2,
                "repeated_failure_reason_stop_threshold": 2,
                "enable_low_risk_bonus_batch": False,
                "estimated_unproductive_continuation_rate": baseline_unproductive,
                "estimated_useful_batches_per_run": useful_per_run,
                "estimated_risk_exposure_index": _round4(high_risk_share + (continue_rate * 0.5)),
            },
            "tuned_policy": {
                **tuned_policy,
                "estimated_unproductive_continuation_rate": tuned_unproductive,
                "estimated_useful_batches_per_run": tuned_useful,
                "estimated_risk_exposure_index": tuned_risk_exposure,
            },
            "determinism_preserved": True,
            "fail_closed_preserved": True,
        },
        "expected_effect": {
            "useful_work": "improve_or_hold",
            "risk_posture": "equal_or_safer",
            "continuation_behavior": "stricter_when_low_value_or_risk_rises",
        },
        "operator_tuning_signals": operator_tuning_signals,
        "source_refs": sorted(
            set(
                list(observability.get("source_refs", []))
                + list(trend_report.get("source_refs", []))
                + [
                    f"adaptive_execution_observability:{observability['observability_id']}",
                    f"adaptive_execution_trend_report:{trend_report['trend_report_id']}",
                ]
            )
        ),
    }
    _validate_schema(review, "adaptive_execution_policy_review")
    return review


__all__ = [
    "AdaptiveExecutionObservabilityError",
    "build_adaptive_execution_observability",
    "build_adaptive_execution_trend_report",
    "build_adaptive_execution_policy_review",
]
