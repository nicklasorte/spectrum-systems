"""Continuous Evaluation Monitor (Prompt BS).

Builds a governed monitoring layer on top of regression_run_result artifacts
so Spectrum Systems can detect quality drift over time, measure
artifact-oriented reliability, and support error-budget-driven decisions.

Design principles
-----------------
- Fail closed:  invalid input raises an error — no silent skipping.
- Schema-governed:  every monitor record and summary is validated against
  the corresponding JSON Schema before return.
- Deterministic evaluation:  the same inputs always produce the same outputs.
- Auditable:  run_id and suite_id are included in all log messages.

Data-flow
---------
    regression_run_result artifact (JSON file)
                │  build_monitor_record(regression_run_result)
                ▼
    evaluation_monitor_record (schema-validated)
                │
    [one or more records] ──► summarize_monitor_records(records)
                ▼
    evaluation_monitor_summary (schema-validated)

Public API
----------
build_monitor_record(regression_run_result)       → monitor record dict
validate_monitor_record(record)                   → list[str]  (empty = valid)
compute_alert_recommendation(record)              → alert dict
summarize_monitor_records(records)                → summary dict
validate_monitor_summary(summary)                 → list[str]  (empty = valid)
classify_trend(values)                            → "improving" | "stable" | "degrading"
assess_burn_rate(records, thresholds)             → burn-rate dict
run_evaluation_monitor(paths)                     → (records list, summary dict)
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jsonschema import Draft202012Validator, FormatChecker

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCHEMA_DIR = _REPO_ROOT / "contracts" / "schemas"
_MONITOR_RECORD_SCHEMA_PATH = _SCHEMA_DIR / "evaluation_monitor_record.schema.json"
_MONITOR_SUMMARY_SCHEMA_PATH = _SCHEMA_DIR / "evaluation_monitor_summary.schema.json"
_RUN_RESULT_SCHEMA_PATH = _SCHEMA_DIR / "regression_run_result.schema.json"

STATUS_DRIFTED = "drifted"
STATUS_INDETERMINATE = "indeterminate"

SCHEMA_VERSION = "1.0.0"
GENERATOR = "spectrum_systems.modules.runtime.evaluation_monitor"

# Default monitoring policy thresholds
_DEFAULT_THRESHOLDS: Dict[str, float] = {
    # A run with overall_status=fail AND pass_rate below this → critical
    "critical_pass_rate": 0.8,
    # Average drift rate across the window above this → critical
    "critical_drift_rate": 0.2,
    # Fraction of failed runs in window that triggers elevated burn rate
    "elevated_burn_fraction": 0.25,
    # Fraction of failed runs in window that triggers exhausting burn rate
    "exhausting_burn_fraction": 0.5,
}

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class EvaluationMonitorError(Exception):
    """Raised for any evaluation monitor failure. Fail-closed."""


class InvalidRegressionResultError(EvaluationMonitorError):
    """Raised when a regression_run_result fails schema validation."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id() -> str:
    return str(uuid.uuid4())


def _load_schema(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise EvaluationMonitorError(f"Schema file not found: {path}")
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _validate_against_schema(artifact: Any, schema: Dict[str, Any]) -> List[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(artifact), key=lambda e: list(e.absolute_path))
    return [e.message for e in errors]


def _safe_divide(numerator: int, denominator: int) -> float:
    """Return numerator / denominator, or 0.0 when denominator is zero."""
    if denominator == 0:
        return 0.0
    return numerator / denominator


# ---------------------------------------------------------------------------
# Public API — single-record operations
# ---------------------------------------------------------------------------


def build_monitor_record(
    regression_run_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a schema-validated evaluation_monitor_record from one run result.

    Parameters
    ----------
    regression_run_result:
        A regression_run_result artifact dict (must be schema-valid).

    Returns
    -------
    dict
        Schema-validated evaluation_monitor_record.

    Raises
    ------
    InvalidRegressionResultError
        If *regression_run_result* fails schema validation.
    EvaluationMonitorError
        If the produced record fails schema validation (should not occur).
    """
    run_id = regression_run_result.get("run_id", "<unknown>")
    suite_id = regression_run_result.get("suite_id", "<unknown>")
    logger.info("Building monitor record run_id=%s suite_id=%s", run_id, suite_id)

    # Validate input
    errors = _validate_input(regression_run_result)
    if errors:
        raise InvalidRegressionResultError(
            f"regression_run_result run_id={run_id} failed schema validation: "
            + "; ".join(errors)
        )

    results: List[Dict[str, Any]] = regression_run_result.get("results", [])
    total = regression_run_result["total_traces"]
    passed = regression_run_result["passed_traces"]
    failed = regression_run_result["failed_traces"]
    pass_rate = regression_run_result["pass_rate"]
    overall_status = regression_run_result["overall_status"]
    summary_block = regression_run_result.get("summary", {})
    drift_counts: Dict[str, int] = dict(summary_block.get("drift_counts", {}))
    avg_repro = summary_block.get("average_reproducibility_score", 0.0)

    # Compute SLI snapshot
    drifted_count = sum(
        1 for r in results if r.get("decision_status") == STATUS_DRIFTED
    )
    indeterminate_count = sum(
        1 for r in results if r.get("decision_status") == STATUS_INDETERMINATE
    )
    drift_rate = _safe_divide(drifted_count, total)

    sli_snapshot = {
        "regression_pass_rate": pass_rate,
        "drift_rate": drift_rate,
        "average_reproducibility_score": avg_repro,
    }

    # Build partial record for alert computation (fields needed by the policy)
    partial_record: Dict[str, Any] = {
        "overall_status": overall_status,
        "pass_rate": pass_rate,
        "sli_snapshot": sli_snapshot,
    }
    alert_recommendation = compute_alert_recommendation(partial_record)

    record: Dict[str, Any] = {
        "monitor_record_id": _new_id(),
        "source_run_id": run_id,
        "source_suite_id": suite_id,
        "created_at": _now_iso(),
        "total_traces": total,
        "passed_traces": passed,
        "failed_traces": failed,
        "pass_rate": pass_rate,
        "average_reproducibility_score": avg_repro,
        "drift_counts": drift_counts,
        "indeterminate_count": indeterminate_count,
        "overall_status": overall_status,
        "sli_snapshot": sli_snapshot,
        "alert_recommendation": alert_recommendation,
        "metadata": {
            "schema_version": SCHEMA_VERSION,
            "generator": GENERATOR,
        },
    }

    validation_errors = validate_monitor_record(record)
    if validation_errors:
        raise EvaluationMonitorError(
            f"Produced monitor record failed schema validation: "
            + "; ".join(validation_errors)
        )

    logger.info(
        "Monitor record built run_id=%s suite_id=%s alert_level=%s",
        run_id,
        suite_id,
        alert_recommendation["level"],
    )
    return record


def _validate_input(regression_run_result: Any) -> List[str]:
    """Validate *regression_run_result* against its schema."""
    schema = _load_schema(_RUN_RESULT_SCHEMA_PATH)
    return _validate_against_schema(regression_run_result, schema)


def validate_monitor_record(record: Any) -> List[str]:
    """Validate *record* against the evaluation_monitor_record JSON Schema.

    Parameters
    ----------
    record:
        Object to validate.

    Returns
    -------
    list[str]
        Validation error messages. Empty list means the record is valid.
    """
    schema = _load_schema(_MONITOR_RECORD_SCHEMA_PATH)
    return _validate_against_schema(record, schema)


def compute_alert_recommendation(
    record: Dict[str, Any],
    thresholds: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Compute an alert recommendation given a (partial) monitor record.

    Applies the initial conservative monitoring policy rules:
    - critical if overall_status=fail AND pass_rate < critical_pass_rate threshold
    - warning if trend-degradation signals are present without crossing critical
    - none otherwise

    Parameters
    ----------
    record:
        Must contain ``overall_status``, ``pass_rate``, and ``sli_snapshot``.
    thresholds:
        Optional override for policy thresholds. Missing keys fall back to
        ``_DEFAULT_THRESHOLDS``.

    Returns
    -------
    dict
        ``{"level": ..., "reasons": [...]}``
    """
    t = dict(_DEFAULT_THRESHOLDS)
    if thresholds:
        t.update(thresholds)

    overall_status = record.get("overall_status", "pass")
    pass_rate = record.get("pass_rate", 1.0)
    sli = record.get("sli_snapshot", {})
    drift_rate = sli.get("drift_rate", 0.0)

    reasons: List[str] = []
    level = "none"

    # Critical: failed run with pass_rate below threshold
    if overall_status == "fail" and pass_rate < t["critical_pass_rate"]:
        level = "critical"
        reasons.append(
            f"overall_status=fail with pass_rate={pass_rate:.3f} below "
            f"threshold={t['critical_pass_rate']:.3f}"
        )

    # Critical: drift rate exceeds threshold
    if drift_rate > t["critical_drift_rate"]:
        if level != "critical":
            level = "critical"
        reasons.append(
            f"drift_rate={drift_rate:.3f} exceeds threshold={t['critical_drift_rate']:.3f}"
        )

    # Warning: run failed but pass_rate is at or above the critical threshold
    if level == "none" and overall_status == "fail":
        level = "warning"
        reasons.append(
            f"overall_status=fail with pass_rate={pass_rate:.3f} "
            f"(above critical threshold={t['critical_pass_rate']:.3f})"
        )

    return {"level": level, "reasons": reasons}


# ---------------------------------------------------------------------------
# Public API — trend classification
# ---------------------------------------------------------------------------


def classify_trend(values: List[float]) -> str:
    """Classify the trend direction of a time-ordered sequence of values.

    Uses a conservative rule: only classify as "improving" or "degrading"
    when the last value is strictly better/worse than the first AND the
    overall direction is monotonically consistent. Otherwise returns "stable".

    Parameters
    ----------
    values:
        Time-ordered list of numeric values (oldest first).  At least two
        elements are required; single-element or empty lists return "stable".

    Returns
    -------
    str
        One of ``"improving"``, ``"stable"``, or ``"degrading"``.
    """
    if len(values) < 2:
        return "stable"

    first = values[0]
    last = values[-1]

    if last == first:
        return "stable"

    # Check if all consecutive steps are in the same direction as the net change
    net_positive = last > first
    for i in range(1, len(values)):
        step_positive = values[i] > values[i - 1]
        step_equal = values[i] == values[i - 1]
        if not step_equal and step_positive != net_positive:
            # Mixed direction — conservative: stable
            return "stable"

    return "improving" if net_positive else "degrading"


# ---------------------------------------------------------------------------
# Public API — burn-rate assessment
# ---------------------------------------------------------------------------


def assess_burn_rate(
    records: List[Dict[str, Any]],
    thresholds: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Compute a simple, deterministic burn-rate assessment for a set of records.

    Rules (applied in order, first match wins):
    - ``exhausting`` if the fraction of failed runs ≥ exhausting_burn_fraction
    - ``elevated``   if the fraction of failed runs ≥ elevated_burn_fraction
    - ``normal``     otherwise

    Parameters
    ----------
    records:
        List of evaluation_monitor_record dicts.
    thresholds:
        Optional override for policy thresholds.

    Returns
    -------
    dict
        ``{"status": ..., "reasons": [...]}``
    """
    t = dict(_DEFAULT_THRESHOLDS)
    if thresholds:
        t.update(thresholds)

    if not records:
        return {"status": "normal", "reasons": ["No records to assess."]}

    total = len(records)
    failed_count = sum(1 for r in records if r.get("overall_status") == "fail")
    failed_fraction = _safe_divide(failed_count, total)

    reasons: List[str] = []

    if failed_fraction >= t["exhausting_burn_fraction"]:
        status = "exhausting"
        reasons.append(
            f"{failed_count}/{total} runs failed "
            f"(fraction={failed_fraction:.2f} ≥ threshold={t['exhausting_burn_fraction']:.2f})"
        )
    elif failed_fraction >= t["elevated_burn_fraction"]:
        status = "elevated"
        reasons.append(
            f"{failed_count}/{total} runs failed "
            f"(fraction={failed_fraction:.2f} ≥ threshold={t['elevated_burn_fraction']:.2f})"
        )
    else:
        status = "normal"

    return {"status": status, "reasons": reasons}


# ---------------------------------------------------------------------------
# Public API — summary
# ---------------------------------------------------------------------------


def summarize_monitor_records(
    records: List[Dict[str, Any]],
    thresholds: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Aggregate a list of monitor records into a schema-validated summary.

    Parameters
    ----------
    records:
        Non-empty list of evaluation_monitor_record dicts (must already be
        schema-valid).
    thresholds:
        Optional override for policy thresholds.

    Returns
    -------
    dict
        Schema-validated evaluation_monitor_summary.

    Raises
    ------
    EvaluationMonitorError
        If *records* is empty or the produced summary fails schema validation.
    """
    if not records:
        raise EvaluationMonitorError(
            "summarize_monitor_records requires at least one record."
        )

    total_runs = len(records)

    # --- Aggregates ---
    pass_rates = [r["pass_rate"] for r in records]
    drift_rates = [r["sli_snapshot"]["drift_rate"] for r in records]
    repro_scores = [r["average_reproducibility_score"] for r in records]
    created_ats = sorted(r["created_at"] for r in records)

    avg_pass_rate = sum(pass_rates) / total_runs
    avg_drift_rate = sum(drift_rates) / total_runs
    avg_repro = sum(repro_scores) / total_runs
    total_failed_runs = sum(1 for r in records if r["overall_status"] == "fail")
    total_critical_alerts = sum(
        1 for r in records if r["alert_recommendation"]["level"] == "critical"
    )

    # --- Trends ---
    pass_rate_trend = classify_trend(pass_rates)
    # For drift rate: higher is worse → "improving" means decreasing
    drift_rate_trend_raw = classify_trend(drift_rates)
    drift_rate_trend = _invert_trend(drift_rate_trend_raw)

    repro_trend = classify_trend(repro_scores)

    # --- Burn rate ---
    burn_rate = assess_burn_rate(records, thresholds)

    # --- Recommended action ---
    recommended_action = _derive_recommended_action(
        records=records,
        burn_rate_status=burn_rate["status"],
        pass_rate_trend=pass_rate_trend,
        total_critical_alerts=total_critical_alerts,
    )

    # --- Source run IDs ---
    source_run_ids = [r["source_run_id"] for r in records]

    summary: Dict[str, Any] = {
        "summary_id": _new_id(),
        "created_at": _now_iso(),
        "window": {
            "start_at": created_ats[0],
            "end_at": created_ats[-1],
            "total_runs": total_runs,
        },
        "aggregates": {
            "average_pass_rate": avg_pass_rate,
            "average_drift_rate": avg_drift_rate,
            "average_reproducibility_score": avg_repro,
            "total_failed_runs": total_failed_runs,
            "total_critical_alerts": total_critical_alerts,
        },
        "trend_analysis": {
            "pass_rate_trend": pass_rate_trend,
            "drift_rate_trend": drift_rate_trend,
            "reproducibility_trend": repro_trend,
        },
        "burn_rate_assessment": burn_rate,
        "recommended_action": recommended_action,
        "source_run_ids": source_run_ids,
    }

    validation_errors = validate_monitor_summary(summary)
    if validation_errors:
        raise EvaluationMonitorError(
            "Produced monitor summary failed schema validation: "
            + "; ".join(validation_errors)
        )

    logger.info(
        "Monitor summary built total_runs=%d recommended_action=%s burn_rate=%s",
        total_runs,
        recommended_action,
        burn_rate["status"],
    )
    return summary


def _invert_trend(trend: str) -> str:
    """Invert a trend direction (used for metrics where lower is better)."""
    if trend == "improving":
        return "degrading"
    if trend == "degrading":
        return "improving"
    return "stable"


def _derive_recommended_action(
    *,
    records: List[Dict[str, Any]],
    burn_rate_status: str,
    pass_rate_trend: str,
    total_critical_alerts: int,
) -> str:
    """Derive the recommended_action from monitoring policy rules.

    Rules (in priority order):
    1. rollback_candidate: critical alerts AND degrading pass_rate trend
    2. freeze_changes:     elevated or exhausting burn rate
    3. watch:              warning-level trend degradation without critical alerts
    4. none:               healthy state
    """
    has_critical = total_critical_alerts > 0
    degrading = pass_rate_trend == "degrading"

    if has_critical and degrading:
        return "rollback_candidate"
    if burn_rate_status in ("elevated", "exhausting"):
        return "freeze_changes"
    if degrading:
        return "watch"
    # Check if any record has a warning-level alert
    has_warning = any(
        r["alert_recommendation"]["level"] == "warning" for r in records
    )
    if has_warning:
        return "watch"
    return "none"


def validate_monitor_summary(summary: Any) -> List[str]:
    """Validate *summary* against the evaluation_monitor_summary JSON Schema.

    Parameters
    ----------
    summary:
        Object to validate.

    Returns
    -------
    list[str]
        Validation error messages. Empty list means the summary is valid.
    """
    schema = _load_schema(_MONITOR_SUMMARY_SCHEMA_PATH)
    return _validate_against_schema(summary, schema)


# ---------------------------------------------------------------------------
# Public API — batch entry point
# ---------------------------------------------------------------------------


def run_evaluation_monitor(
    regression_run_result_paths: List[str | Path],
    thresholds: Optional[Dict[str, float]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Ingest one or more regression_run_result files and produce monitor artifacts.

    Parameters
    ----------
    regression_run_result_paths:
        Paths to regression_run_result JSON files. Must be non-empty.
    thresholds:
        Optional policy threshold overrides.

    Returns
    -------
    tuple[list[dict], dict]
        ``(records, summary)`` where *records* is a list of
        evaluation_monitor_record dicts and *summary* is the
        evaluation_monitor_summary dict.

    Raises
    ------
    EvaluationMonitorError
        If no paths are provided.
    InvalidRegressionResultError
        If any input file is missing or fails schema validation.
    """
    if not regression_run_result_paths:
        raise EvaluationMonitorError(
            "run_evaluation_monitor requires at least one regression_run_result path."
        )

    records: List[Dict[str, Any]] = []
    for raw_path in regression_run_result_paths:
        path = Path(raw_path)
        if not path.is_file():
            raise InvalidRegressionResultError(
                f"regression_run_result file not found: {path}"
            )
        with path.open(encoding="utf-8") as fh:
            try:
                run_result = json.load(fh)
            except json.JSONDecodeError as exc:
                raise InvalidRegressionResultError(
                    f"Failed to parse regression_run_result JSON from '{path}': {exc}"
                ) from exc

        record = build_monitor_record(run_result)
        records.append(record)

    summary = summarize_monitor_records(records, thresholds=thresholds)
    return records, summary
