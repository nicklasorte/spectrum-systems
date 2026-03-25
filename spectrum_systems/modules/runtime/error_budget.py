"""Deterministic error budget status computation from SLO + observability artifacts."""

from __future__ import annotations

import hashlib
import json
import collections
from copy import deepcopy
from pathlib import Path
from typing import Any, Deque, Dict, Optional, Tuple

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema

SCHEMA_VERSION = "1.0.0"
_GENERATED_BY_VERSION = "error_budget.py@1.0.0"
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_POLICY_PATH = _REPO_ROOT / "data" / "policy" / "error_budget_policy.json"

_METRIC_VOCAB = frozenset(
    {
        "replay_success_rate",
        "grounding_block_rate",
        "unsupported_claim_rate",
        "invalid_evidence_ref_rate",
        "drift_exceed_threshold_rate",
        "baseline_gate_block_rate",
        "regression_failure_rate",
    }
)

_DEFAULT_WINDOW: int = 100
_FAILURE_THRESHOLD: float = 0.95
_GOVERNED_SLIS = (
    "completeness",
    "timeliness",
    "traceability",
    "traceability_integrity",
)


class ErrorBudgetError(ValueError):
    """Raised when deterministic error-budget computation fails closed."""


def _validate_or_raise(instance: Dict[str, Any], schema_name: str, *, context: str) -> None:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise ErrorBudgetError(f"{context} failed validation: {details}")


def _stable_id(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _require_non_empty_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ErrorBudgetError(f"{field_name} must be a non-empty string")
    return value


def _require_ratio(value: Any, field_name: str) -> float:
    ratio = float(value)
    if ratio < 0.0 or ratio > 1.0:
        raise ErrorBudgetError(f"{field_name} must be between 0.0 and 1.0")
    return ratio


def load_error_budget_policy(policy_path: Path | None = None) -> Dict[str, Any]:
    """Load governed error budget policy from data/policy."""
    path = policy_path or _DEFAULT_POLICY_PATH
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ErrorBudgetError(f"error budget policy not found: {path}") from exc
    except OSError as exc:
        raise ErrorBudgetError(f"failed reading error budget policy: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ErrorBudgetError(f"error budget policy is not valid JSON: {exc}") from exc

    _validate_or_raise(policy, "error_budget_policy", context="error_budget_policy")
    return policy


def _resolve_policy(policy: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if policy is None:
        return {
            "artifact_type": "error_budget_policy",
            "schema_version": "1.0.0",
            "policy_id": "error-budget-policy-default-v1",
            "measurement_window": "single_run",
            "supported_metrics": sorted(_METRIC_VOCAB),
            "warning_consumption_ratio": 0.5,
            "exhausted_consumption_ratio": 1.0,
            "unknown_metric_handling": "fail_closed",
            "missing_metric_handling": "fail_closed",
            "generated_by_version": "error_budget_policy.default@1.0.0",
        }
    _validate_or_raise(policy, "error_budget_policy", context="error_budget_policy")
    resolved = deepcopy(policy)
    if float(resolved["exhausted_consumption_ratio"]) < float(resolved["warning_consumption_ratio"]):
        raise ErrorBudgetError("error_budget_policy.exhausted_consumption_ratio must be >= warning_consumption_ratio")
    return resolved


def _compute_error_terms(*, operator: str, target_value: float, observed_value: float) -> Dict[str, float]:
    if operator == "gte":
        allowed_error = round(max(0.0, 1.0 - target_value), 6)
        consumed_error = round(max(0.0, target_value - observed_value), 6)
    elif operator == "lte":
        allowed_error = round(max(0.0, target_value), 6)
        consumed_error = round(max(0.0, observed_value - target_value), 6)
    elif operator == "eq":
        allowed_error = 0.0
        consumed_error = round(abs(observed_value - target_value), 6)
    else:
        raise ErrorBudgetError(f"unsupported target_operator: {operator!r}")

    remaining_error = round(max(0.0, allowed_error - consumed_error), 6)
    if allowed_error == 0.0:
        consumption_ratio = 1.0 if consumed_error > 0.0 else 0.0
    else:
        consumption_ratio = round(min(1.0, consumed_error / allowed_error), 6)

    return {
        "allowed_error": allowed_error,
        "consumed_error": consumed_error,
        "remaining_error": remaining_error,
        "consumption_ratio": consumption_ratio,
    }


def _status_for_ratio(consumption_ratio: float, policy: Dict[str, Any]) -> str:
    warning_threshold = float(policy["warning_consumption_ratio"])
    exhausted_threshold = float(policy["exhausted_consumption_ratio"])

    if consumption_ratio >= exhausted_threshold:
        return "exhausted"
    if consumption_ratio >= warning_threshold:
        return "warning"
    return "healthy"


def build_error_budget_status(
    observability_metrics: Dict[str, Any],
    slo_definition: Dict[str, Any],
    policy: Optional[Dict[str, Any]] = None,
    *,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a deterministic schema-valid error_budget_status artifact."""
    if not isinstance(observability_metrics, dict):
        raise ErrorBudgetError("observability_metrics must be an object")
    if not isinstance(slo_definition, dict):
        raise ErrorBudgetError("slo_definition must be an object")

    observability = deepcopy(observability_metrics)
    slo = deepcopy(slo_definition)
    resolved_policy = _resolve_policy(policy)

    _validate_or_raise(observability, "observability_metrics", context="observability_metrics")
    _validate_or_raise(slo, "service_level_objective", context="service_level_objective")

    if observability.get("slo_id") != slo.get("slo_id"):
        raise ErrorBudgetError("observability_metrics.slo_id must match service_level_objective.slo_id")

    if observability.get("metric_window") != str(resolved_policy.get("measurement_window")):
        raise ErrorBudgetError(
            "observability_metrics.metric_window must match error_budget_policy.measurement_window"
        )

    supported_metrics = set(resolved_policy.get("supported_metrics") or [])
    if not supported_metrics:
        raise ErrorBudgetError("error_budget_policy.supported_metrics must not be empty")

    objectives = []
    reasons = []
    triggered_conditions = []

    observed_metrics = observability.get("metrics") or {}

    for objective in slo.get("objectives") or []:
        metric_name = str(objective.get("metric_name"))
        if metric_name not in _METRIC_VOCAB:
            raise ErrorBudgetError(f"unsupported metric vocabulary in SLO objective: {metric_name!r}")
        if metric_name not in supported_metrics:
            raise ErrorBudgetError(f"SLO objective metric not allowed by policy: {metric_name!r}")
        if metric_name not in observed_metrics:
            raise ErrorBudgetError(
                f"SLO objective metric {metric_name!r} is not present in observability_metrics.metrics"
            )

        target_value = _require_ratio(objective.get("target_value"), f"objective[{metric_name}].target_value")
        observed_value = _require_ratio(observed_metrics.get(metric_name), f"metrics.{metric_name}")

        terms = _compute_error_terms(
            operator=str(objective.get("target_operator")),
            target_value=target_value,
            observed_value=observed_value,
        )
        objective_status = _status_for_ratio(terms["consumption_ratio"], resolved_policy)

        objective_record = {
            "metric_name": metric_name,
            "target_value": target_value,
            "observed_value": observed_value,
            "allowed_error": terms["allowed_error"],
            "consumed_error": terms["consumed_error"],
            "remaining_error": terms["remaining_error"],
            "consumption_ratio": terms["consumption_ratio"],
            "status": objective_status,
        }
        objectives.append(objective_record)

        if objective_status in {"warning", "exhausted"}:
            triggered_conditions.append(
                {
                    "metric_name": metric_name,
                    "status": objective_status,
                    "consumption_ratio": terms["consumption_ratio"],
                }
            )
            reasons.append(
                f"{metric_name} consumption_ratio={terms['consumption_ratio']:.6f} status={objective_status}"
            )

    severity_rank = {"healthy": 0, "warning": 1, "exhausted": 2, "invalid": 3}
    highest = "healthy"
    for item in objectives:
        if severity_rank[item["status"]] > severity_rank[highest]:
            highest = item["status"]

    resolved_trace_id = trace_id or (observability.get("trace_refs") or {}).get("trace_id")

    result = {
        "artifact_id": "",
        "artifact_type": "error_budget_status",
        "schema_version": SCHEMA_VERSION,
        "timestamp": _require_non_empty_str(observability.get("timestamp"), "observability_metrics.timestamp"),
        "trace_refs": {
            "trace_id": _require_non_empty_str(resolved_trace_id, "trace_id"),
        },
        "slo_id": _require_non_empty_str(slo.get("slo_id"), "slo_id"),
        "observability_metrics_id": _require_non_empty_str(observability.get("artifact_id"), "observability_metrics_id"),
        "policy_id": _require_non_empty_str(str(resolved_policy.get("policy_id")), "policy_id"),
        "budget_window": _require_non_empty_str(observability.get("metric_window"), "budget_window"),
        "budget_status": highest,
        "objectives": objectives,
        "highest_severity": highest,
        "triggered_conditions": triggered_conditions,
        "reasons": reasons,
        "generated_by_version": _GENERATED_BY_VERSION,
    }

    preimage = dict(result)
    preimage.pop("artifact_id", None)
    result["artifact_id"] = _stable_id(preimage)

    _validate_or_raise(result, "error_budget_status", context="error_budget_status")
    return result


class ErrorBudgetTracker:
    """Compatibility tracker retained for BN.6/BH–BJ control-layer callers.

    This class preserves the historical rolling-window API used by control
    modules while coexisting with the governed error_budget_status artifact
    builder in this module.
    """

    def __init__(
        self,
        window_size: int = _DEFAULT_WINDOW,
        failure_threshold: float = _FAILURE_THRESHOLD,
    ) -> None:
        self._window_size = max(1, int(window_size))
        self._failure_threshold = float(failure_threshold)
        self._runs: Deque[Tuple[str, str, Dict[str, float]]] = collections.deque(
            maxlen=self._window_size
        )

    def update_error_budget(
        self,
        run_id: str,
        slo_status: str,
        slis: Dict[str, float],
    ) -> None:
        if not isinstance(slis, dict):
            raise ErrorBudgetError("slis must be an object")
        normalized_slis: Dict[str, float] = {}
        for name in _GOVERNED_SLIS:
            raw = slis.get(name, 0.0)
            try:
                value = float(raw)
            except (TypeError, ValueError) as exc:
                raise ErrorBudgetError(f"sli {name!r} must be numeric") from exc
            if value < 0.0 or value > 1.0:
                raise ErrorBudgetError(f"sli {name!r} must be between 0.0 and 1.0")
            normalized_slis[name] = value
        self._runs.append((str(run_id), str(slo_status), normalized_slis))

    def compute_burn_rate(self) -> Dict[str, float]:
        if not self._runs:
            result: Dict[str, float] = {sli: 0.0 for sli in _GOVERNED_SLIS}
            result["overall"] = 0.0
            return result

        n = len(self._runs)
        failure_counts: Dict[str, int] = {sli: 0 for sli in _GOVERNED_SLIS}
        for _run_id, _slo_status, slis in self._runs:
            for sli in _GOVERNED_SLIS:
                if float(slis.get(sli, 0.0)) < self._failure_threshold:
                    failure_counts[sli] += 1

        burn_rates: Dict[str, float] = {sli: round(failure_counts[sli] / n, 6) for sli in _GOVERNED_SLIS}
        burn_rates["overall"] = round(sum(burn_rates[sli] for sli in _GOVERNED_SLIS) / len(_GOVERNED_SLIS), 6)
        return burn_rates

    def window_size(self) -> int:
        return self._window_size

    def run_count(self) -> int:
        return len(self._runs)


_default_tracker: ErrorBudgetTracker = ErrorBudgetTracker()


def update_error_budget(
    run_id: str,
    slo_status: str,
    slis: Dict[str, float],
    tracker: Optional[ErrorBudgetTracker] = None,
) -> None:
    (tracker or _default_tracker).update_error_budget(run_id, slo_status, slis)


def compute_burn_rate(
    tracker: Optional[ErrorBudgetTracker] = None,
) -> Dict[str, float]:
    return (tracker or _default_tracker).compute_burn_rate()
