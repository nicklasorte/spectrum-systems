"""Shared canonical replay_result fixture builder for runtime tests."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Dict, Optional

from spectrum_systems.contracts import load_example, load_schema

_DEFAULT_REPLAY_METRICS = ("replay_success_rate",)
_HIGHER_IS_BETTER_METRICS = frozenset({"replay_success_rate"})


def _current_replay_schema_version() -> str:
    schema = load_schema("replay_result")
    return str(schema["properties"]["schema_version"].get("const") or "")


def _stable_artifact_id(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

def _deep_merge(base: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def enforce_replay_budget_consistency(result: Dict[str, Any]) -> Dict[str, Any]:
    """Recompute replay budget state and fail fast if metric/objective invariants remain broken."""
    align_replay_budget_with_observability(result)
    observability = result.get("observability_metrics")
    budget = result.get("error_budget_status")
    if not isinstance(observability, dict) or not isinstance(budget, dict):
        return result
    metrics = observability.get("metrics")
    objectives = budget.get("objectives")
    if not isinstance(metrics, dict) or not isinstance(objectives, list):
        return result

    supported_statuses = {"healthy", "warning", "exhausted", "invalid"}
    severity_rank = {"healthy": 0, "warning": 1, "exhausted": 2, "invalid": 3}

    computed_highest = "healthy"
    objective_by_metric = {}
    for objective in objectives:
        if not isinstance(objective, dict):
            continue
        metric_name = str(objective.get("metric_name") or "")
        objective_by_metric[metric_name] = objective
    required_metrics = sorted(
        metric_name for metric_name in metrics.keys() if metric_name != "total_runs"
    )
    for metric_name in required_metrics:
        objective = objective_by_metric.get(metric_name)
        if not isinstance(objective, dict):
            raise ValueError(
                f"budget consistency mismatch for {metric_name}: missing error_budget_status objective"
            )
        metric_value = metrics.get(metric_name)
        observed_value = objective.get("observed_value")
        if not isinstance(metric_value, (int, float)) or not isinstance(observed_value, (int, float)):
            raise ValueError(f"budget consistency mismatch for {metric_name}: missing numeric observed values")
        if abs(float(metric_value) - float(observed_value)) > 1e-9:
            raise ValueError(
                f"budget consistency mismatch for {metric_name}: metric={metric_value} observed={observed_value}"
            )
        status = str(objective.get("status") or "")
        if status not in supported_statuses:
            raise ValueError(f"unsupported objective status: {status!r}")
        if severity_rank[status] > severity_rank[computed_highest]:
            computed_highest = status

    budget_status = str(budget.get("budget_status") or "")
    highest_severity = str(budget.get("highest_severity") or "")
    if budget_status not in supported_statuses:
        raise ValueError(f"unsupported budget_status value: {budget_status!r}")
    if highest_severity not in supported_statuses:
        raise ValueError(f"unsupported highest_severity value: {highest_severity!r}")
    if budget_status != highest_severity:
        raise ValueError(
            f"budget consistency mismatch: budget_status={budget_status!r} highest_severity={highest_severity!r}"
        )
    if budget_status != "invalid" and budget_status != computed_highest:
        raise ValueError(
            f"budget consistency mismatch: budget_status={budget_status!r} computed_highest={computed_highest!r}"
        )
    return result


def align_replay_budget_with_observability(result: Dict[str, Any]) -> Dict[str, Any]:
    """Mutate and return replay_result with metric/objective budget consistency."""
    observability = result.get("observability_metrics")
    budget = result.get("error_budget_status")
    if not isinstance(observability, dict) or not isinstance(budget, dict):
        return result
    metrics = observability.get("metrics")
    objectives = budget.get("objectives")
    if not isinstance(metrics, dict) or not isinstance(objectives, list):
        return result

    severity_rank = {"healthy": 0, "warning": 1, "exhausted": 2, "invalid": 3}
    highest = "healthy"
    triggered_conditions = []
    reasons = []

    for objective in objectives:
        if not isinstance(objective, dict):
            continue
        metric_name = objective.get("metric_name")
        if metric_name not in metrics or metric_name == "total_runs":
            continue
        observed_metric = metrics.get(metric_name)
        if not isinstance(observed_metric, (int, float)):
            continue
        observed_value = float(observed_metric)
        objective["observed_value"] = observed_value
        target_value = float(objective.get("target_value", 0.0))
        allowed_error = float(objective.get("allowed_error", 0.0))
        if metric_name in _HIGHER_IS_BETTER_METRICS:
            consumed_error = round(max(0.0, target_value - observed_value), 6)
        else:
            consumed_error = round(max(0.0, observed_value - target_value), 6)
        remaining_error = round(max(0.0, allowed_error - consumed_error), 6)
        if allowed_error <= 0.0:
            consumption_ratio = 1.0 if consumed_error > 0.0 else 0.0
        else:
            consumption_ratio = round(min(1.0, consumed_error / allowed_error), 6)
        if consumption_ratio >= 1.0:
            status = "exhausted"
        elif consumption_ratio >= 0.5:
            status = "warning"
        else:
            status = "healthy"
        objective["consumed_error"] = consumed_error
        objective["remaining_error"] = remaining_error
        objective["consumption_ratio"] = consumption_ratio
        objective["status"] = status

        if severity_rank[status] > severity_rank[highest]:
            highest = status
        if status in {"warning", "exhausted"}:
            triggered_conditions.append(
                {
                    "metric_name": metric_name,
                    "status": status,
                    "consumption_ratio": consumption_ratio,
                }
            )
            reasons.append(f"{metric_name} consumption_ratio={consumption_ratio:.6f} status={status}")

    budget["budget_status"] = highest
    budget["highest_severity"] = highest
    budget["triggered_conditions"] = triggered_conditions
    budget["reasons"] = reasons
    return result


def align_replay_budget_state(
    result: Dict[str, Any],
    *,
    budget_status: str,
) -> Dict[str, Any]:
    """Force a budget status while keeping objective and summary fields internally consistent."""
    align_replay_budget_with_observability(result)
    observability = result.get("observability_metrics")
    budget = result.get("error_budget_status")
    if not isinstance(observability, dict) or not isinstance(budget, dict):
        return result
    metrics = observability.get("metrics")
    objectives = budget.get("objectives")
    if not isinstance(metrics, dict) or not isinstance(objectives, list):
        return result

    for objective in objectives:
        if not isinstance(objective, dict):
            continue
        metric_name = objective.get("metric_name")
        if metric_name == "replay_success_rate":
            target = float(objective.get("target_value", 0.0))
            allowed = float(objective.get("allowed_error", 0.0))
            if budget_status == "healthy":
                observed_value = target
            elif budget_status == "warning":
                observed_value = target - (allowed * 0.6 if allowed > 0.0 else 0.0)
            elif budget_status == "exhausted":
                observed_value = target - allowed - 0.01
            else:
                continue
            metrics[metric_name] = float(observed_value)
        elif metric_name == "drift_exceed_threshold_rate":
            target = float(objective.get("target_value", 0.0))
            allowed = float(objective.get("allowed_error", 0.0))
            if budget_status == "healthy":
                observed_value = target
            elif budget_status == "warning":
                observed_value = target + (allowed * 0.6 if allowed > 0.0 else 0.01)
            elif budget_status == "exhausted":
                observed_value = target + allowed + 0.01
            else:
                continue
            metrics[metric_name] = float(observed_value)

    align_replay_budget_with_observability(result)
    if budget_status == "invalid":
        budget["budget_status"] = "invalid"
        budget["highest_severity"] = "invalid"
        budget["triggered_conditions"] = []
        budget["reasons"] = []
    return result


def _apply_budget_patch(result: Dict[str, Any], budget_patch: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not budget_patch or not isinstance(result.get("error_budget_status"), dict):
        return result
    budget = result["error_budget_status"]
    observed_values = budget_patch.get("observed_values")
    if isinstance(observed_values, dict) and isinstance(result.get("observability_metrics"), dict):
        metrics = result["observability_metrics"].get("metrics")
        budget_objectives = budget.get("objectives")
        if isinstance(metrics, dict):
            for metric_name, observed_value in observed_values.items():
                if isinstance(observed_value, (int, float)):
                    metrics[metric_name] = float(observed_value)
            if isinstance(budget_objectives, list):
                existing = {
                    str(item.get("metric_name"))
                    for item in budget_objectives
                    if isinstance(item, dict) and isinstance(item.get("metric_name"), str)
                }
                for metric_name in metrics.keys():
                    if metric_name == "total_runs" or metric_name in existing:
                        continue
                    target_value = 0.99 if metric_name in _HIGHER_IS_BETTER_METRICS else 0.05
                    budget_objectives.append(
                        {
                            "metric_name": metric_name,
                            "target_value": target_value,
                            "observed_value": float(metrics[metric_name]),
                            "allowed_error": round(max(0.0, 1.0 - target_value) if metric_name in _HIGHER_IS_BETTER_METRICS else target_value, 6),
                            "consumed_error": 0.0,
                            "remaining_error": 0.0,
                            "consumption_ratio": 0.0,
                            "status": "healthy",
                        }
                    )
        enforce_replay_budget_consistency(result)
    budget_status = budget_patch.get("budget_status")
    if isinstance(budget_status, str):
        align_replay_budget_state(result, budget_status=budget_status)
        enforce_replay_budget_consistency(result)
    return result


def make_canonical_replay_result(
    *,
    replay_id: str = "RPL-test-001",
    trace_id: str = "trace-eval-001",
    original_run_id: str = "eval-run-001",
    replay_run_id: str = "eval-run-001",
    overrides: Optional[Dict[str, Any]] = None,
    budget_patch: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return a minimal schema-valid replay_result payload for tests.

    Invariant: ``observability_metrics.metrics`` values must equal
    ``error_budget_status.objectives[*].observed_value`` for governed metrics.
    """
    observability = deepcopy(load_example("observability_metrics"))
    observability["trace_refs"]["trace_id"] = trace_id
    observability["metrics"] = {
        "total_runs": 1,
        "replay_success_rate": float(observability["metrics"].get("replay_success_rate", 1.0)),
    }

    error_budget = deepcopy(load_example("error_budget_status"))
    error_budget["trace_refs"]["trace_id"] = trace_id
    error_budget["observability_metrics_id"] = observability["artifact_id"]
    error_budget["objectives"] = [
        objective
        for objective in error_budget.get("objectives", [])
        if isinstance(objective, dict) and objective.get("metric_name") in set(_DEFAULT_REPLAY_METRICS)
    ]

    result: Dict[str, Any] = {
        "artifact_id": "",
        "artifact_type": "replay_result",
        "schema_version": _current_replay_schema_version(),
        "replay_id": replay_id,
        "original_run_id": original_run_id,
        "replay_run_id": replay_run_id,
        "timestamp": "2026-03-22T00:00:00Z",
        "trace_id": trace_id,
        "input_artifact_reference": "eval_summary:eval-run-001",
        "original_decision_reference": "ECD-eval-run-001-ALLOW",
        "original_enforcement_reference": "ENF-000000000001",
        "replay_decision_reference": "ECD-eval-run-001-ALLOW",
        "replay_enforcement_reference": "ENF-000000000002",
        "replay_decision": "allow",
        "replay_enforcement_action": "allow_execution",
        "replay_final_status": "allow",
        "original_enforcement_action": "allow_execution",
        "original_final_status": "allow",
        "consistency_status": "match",
        "drift_detected": False,
        "failure_reason": None,
        "replay_path": "bag_replay_engine",
        "provenance": {
            "source_artifact_type": "eval_summary",
            "source_artifact_id": "eval-run-001",
            "trace_id": trace_id,
        },
        "observability_metrics": observability,
        "error_budget_status": error_budget,
    }
    enforce_replay_budget_consistency(result)
    _apply_budget_patch(result, budget_patch)
    result["artifact_id"] = _stable_artifact_id({k: v for k, v in result.items() if k != "artifact_id"})
    if overrides:
        merged = _deep_merge(result, overrides)
        if merged.get("consistency_status") == "mismatch":
            merged["drift_detected"] = True
        enforce_replay_budget_consistency(merged)
        _apply_budget_patch(merged, budget_patch)
        enforce_replay_budget_consistency(merged)
        if "artifact_id" not in overrides:
            merged["artifact_id"] = _stable_artifact_id({k: v for k, v in merged.items() if k != "artifact_id"})
        return merged
    if result.get("consistency_status") == "mismatch":
        result["drift_detected"] = True
    enforce_replay_budget_consistency(result)
    _apply_budget_patch(result, budget_patch)
    result["artifact_id"] = _stable_artifact_id({k: v for k, v in result.items() if k != "artifact_id"})
    return result
