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


__all__ = [
    "AdaptiveExecutionObservabilityError",
    "build_adaptive_execution_observability",
    "build_adaptive_execution_trend_report",
]
