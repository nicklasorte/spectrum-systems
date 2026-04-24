"""SLO/SLI definitions for the Spectrum Systems AI Operating Substrate.

Defines the authoritative SLO targets and alert thresholds for the five
core reliability dimensions. All monitoring, alerting, and enforcement gates
reference this module as the single source of truth.

SLOs are wired to the governance enforcement path:
- cost_slo: hard freeze on budget exhaust (enforcement mandatory)
- All others: warn at alert_threshold, critical at target breach
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional

SloStatus = Literal["pass", "warning", "critical"]

# ---------------------------------------------------------------------------
# Authoritative SLO definitions (AI Operating Substrate standard)
# ---------------------------------------------------------------------------

SLO_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "drift_slo": {
        "metric": "drift_signal_max",
        "description": "Maximum acceptable drift signal before escalation",
        "target": 0.15,
        "alert_threshold": 0.10,
        "window": "7d",
        "unit": "ratio",
        "enforcement": "warn_at_alert_threshold",
    },
    "error_budget_slo": {
        "metric": "error_rate",
        "description": "Maximum acceptable error rate over rolling window",
        "target": 0.05,
        "alert_threshold": 0.03,
        "window": "30d",
        "unit": "ratio",
        "enforcement": "warn_at_alert_threshold",
    },
    "latency_slo": {
        "metric": "p99_latency_ms",
        "description": "p99 latency bound for governed execution",
        "target": 5000,
        "alert_threshold": 3000,
        "window": "7d",
        "unit": "milliseconds",
        "enforcement": "warn_at_alert_threshold",
    },
    "cost_slo": {
        "metric": "tokens_per_run",
        "description": "Maximum tokens consumed per governed run",
        "target": 100000,
        "alert_threshold": 80000,
        "window": "24h",
        "unit": "tokens",
        "enforcement": "hard_freeze_on_budget_exhaust",
    },
    "schema_conformance_slo": {
        "metric": "schema_pass_rate",
        "description": "Minimum schema conformance rate for emitted artifacts",
        "target": 0.99,
        "alert_threshold": 0.95,
        "window": "7d",
        "unit": "ratio",
        "enforcement": "warn_at_alert_threshold",
    },
}

# ---------------------------------------------------------------------------
# SLI measurement helpers
# ---------------------------------------------------------------------------

_HIGHER_IS_BETTER = {"schema_pass_rate"}
_LOWER_IS_BETTER = {"drift_signal_max", "error_rate", "p99_latency_ms", "tokens_per_run"}


def _evaluate_status(metric: str, value: float, slo_def: Dict[str, Any]) -> SloStatus:
    """Evaluate the SLO status for a metric value.

    For lower-is-better metrics:
      - value <= alert_threshold  → pass
      - alert_threshold < value <= target → warning
      - value > target → critical

    For higher-is-better metrics (schema_pass_rate):
      - value >= target → pass
      - alert_threshold <= value < target → warning
      - value < alert_threshold → critical
    """
    if metric in _HIGHER_IS_BETTER:
        if value >= slo_def["target"]:
            return "pass"
        if value >= slo_def["alert_threshold"]:
            return "warning"
        return "critical"
    # lower-is-better (default)
    if value <= slo_def["alert_threshold"]:
        return "pass"
    if value <= slo_def["target"]:
        return "warning"
    return "critical"


def emit_slo_metric(
    metric_name: str,
    value: float,
    timestamp: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Emit a governed SLO metric artifact.

    Parameters
    ----------
    metric_name:
        One of the keys in SLO_DEFINITIONS (e.g. 'drift_slo').
    value:
        The measured metric value.
    timestamp:
        RFC3339 timestamp; defaults to current UTC time.
    run_id:
        Optional run identifier for traceability.

    Returns
    -------
    dict
        A slo_metric_artifact dict with status and enforcement signal.

    Raises
    ------
    ValueError
        If metric_name is not defined in SLO_DEFINITIONS.
    """
    slo_def = SLO_DEFINITIONS.get(metric_name)
    if slo_def is None:
        raise ValueError(
            f"Unknown SLO metric: '{metric_name}'. "
            f"Known metrics: {sorted(SLO_DEFINITIONS)}"
        )

    if timestamp is None:
        timestamp = datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()

    metric = slo_def["metric"]
    status = _evaluate_status(metric, value, slo_def)

    enforcement_signal = None
    if slo_def["enforcement"] == "hard_freeze_on_budget_exhaust" and status == "critical":
        enforcement_signal = "hard_freeze_required"
    elif status == "critical":
        enforcement_signal = "critical_breach"
    elif status == "warning":
        enforcement_signal = "alert_threshold_exceeded"

    artifact = {
        "artifact_type": "slo_metric_artifact",
        "schema_version": "1.0.0",
        "slo_name": metric_name,
        "metric_name": metric,
        "value": value,
        "slo_target": slo_def["target"],
        "alert_threshold": slo_def["alert_threshold"],
        "window": slo_def["window"],
        "unit": slo_def.get("unit", ""),
        "status": status,
        "enforcement": slo_def["enforcement"],
        "enforcement_signal": enforcement_signal,
        "timestamp": timestamp,
    }
    if run_id is not None:
        artifact["run_id"] = run_id

    return artifact


def check_all_slos(
    measurements: Dict[str, float],
    timestamp: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Check all provided measurements against their SLO definitions.

    Parameters
    ----------
    measurements:
        Dict mapping slo_name → measured value.
    timestamp:
        Shared RFC3339 timestamp for all metrics.
    run_id:
        Optional run identifier.

    Returns
    -------
    dict
        {overall_status, metrics: {slo_name: slo_metric_artifact}, enforcement_required: bool}
    """
    if timestamp is None:
        timestamp = datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()

    results: Dict[str, Any] = {}
    enforcement_required = False

    for slo_name, value in measurements.items():
        artifact = emit_slo_metric(slo_name, value, timestamp=timestamp, run_id=run_id)
        results[slo_name] = artifact
        if artifact["enforcement_signal"] in ("hard_freeze_required", "critical_breach"):
            enforcement_required = True

    statuses = {a["status"] for a in results.values()}
    if "critical" in statuses:
        overall = "critical"
    elif "warning" in statuses:
        overall = "warning"
    else:
        overall = "pass"

    return {
        "artifact_type": "slo_check_result",
        "schema_version": "1.0.0",
        "overall_status": overall,
        "enforcement_required": enforcement_required,
        "metrics": results,
        "timestamp": timestamp,
    }
