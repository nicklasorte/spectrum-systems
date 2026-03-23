"""Evaluation Budget Governor (Prompt BT).

Consumes evaluation_monitor_summary artifacts and produces governed
evaluation_budget_decision artifacts that control system behavior.

Design principles
-----------------
- Fail closed:  any invalid or missing input raises an error immediately.
- Schema-governed:  every decision artifact is validated before return.
- Deterministic evaluation:  the same inputs always produce the same outputs.
- Multi-signal policy:  decisions combine drift_rate, failure_rate, burn_rate,
  and trend signals — no single-field threshold may block a system on its own.
- Auditable:  all triggered thresholds are recorded in the output artifact.

Data-flow
---------
    evaluation_monitor_summary (JSON file)
                │  load_monitor_summary(path)
                ▼
    summary dict  ──► validate_summary(summary)
                │
                ▼
    evaluate_budget_status(summary, thresholds)
                │
                ▼
    determine_system_response(status, thresholds)
                │
                ▼
    build_decision_artifact(...)
                │  validate_decision(decision)
                ▼
    evaluation_budget_decision (schema-validated)

Public API
----------
load_monitor_summary(path)                        → summary dict
validate_summary(summary)                         → list[str]  (empty = valid)
evaluate_budget_status(summary, thresholds)       → (status, reasons, triggered)
determine_system_response(status, thresholds)     → system_response str
build_decision_artifact(...)                      → decision dict
validate_decision(decision)                       → list[str]  (empty = valid)
run_budget_governor(path, thresholds)             → decision dict
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jsonschema import Draft202012Validator, FormatChecker
from spectrum_systems.modules.runtime.evaluation_control import map_control_loop_status_to_response

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCHEMA_DIR = _REPO_ROOT / "contracts" / "schemas"
_MONITOR_SUMMARY_SCHEMA_PATH = _SCHEMA_DIR / "evaluation_monitor_summary.schema.json"
_BUDGET_DECISION_SCHEMA_PATH = _SCHEMA_DIR / "evaluation_budget_decision.schema.json"

SCHEMA_VERSION = "1.0.0"
GENERATOR = "spectrum_systems.modules.runtime.evaluation_budget_governor"

# Default policy thresholds
_DEFAULT_THRESHOLDS: Dict[str, Any] = {
    # Drift rate thresholds
    "drift_rate_warning": 0.10,   # ≥10 % drift → at least warning
    "drift_rate_critical": 0.25,  # ≥25 % drift → contributes to blocked
    # Failure rate thresholds (total_failed_runs / window.total_runs)
    "failure_rate_warning": 0.20,  # ≥20 % failures → at least warning
    "failure_rate_critical": 0.50, # ≥50 % failures → contributes to blocked
    # Burn rate thresholds (mapped from evaluation_monitor_summary)
    "burn_rate_elevated_triggers_warning": True,
    "burn_rate_exhausting_triggers_exhausted": True,
    # Trend signal
    "degrading_trend_triggers_warning": True,
}

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class EvaluationBudgetGovernorError(Exception):
    """Raised for any budget governor failure. Fail-closed."""


class InvalidSummaryError(EvaluationBudgetGovernorError):
    """Raised when an evaluation_monitor_summary fails schema validation."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id() -> str:
    return str(uuid.uuid4())


def _deterministic_control_decision_id(summary: Dict[str, Any], status: str, triggered: List[str]) -> str:
    seed_payload = {
        "summary_id": summary.get("summary_id"),
        "trace_id": summary.get("trace_id"),
        "overall_status": summary.get("overall_status"),
        "status": status,
        "triggered_thresholds": sorted(triggered),
    }
    seed = json.dumps(seed_payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = uuid.uuid5(uuid.NAMESPACE_URL, seed).hex[:12]
    return f"EBD-{digest}"


def _canonical_timestamp(value: Any) -> str:
    if isinstance(value, str) and value:
        return value
    return "1970-01-01T00:00:00Z"


def _load_schema(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise EvaluationBudgetGovernorError(f"Schema file not found: {path}")
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _validate_against_schema(artifact: Any, schema: Dict[str, Any]) -> List[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(
        validator.iter_errors(artifact), key=lambda e: list(e.absolute_path)
    )
    return [e.message for e in errors]


def _safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


# ---------------------------------------------------------------------------
# Public API — loading and validation
# ---------------------------------------------------------------------------


def load_monitor_summary(path: str | Path) -> Dict[str, Any]:
    """Load and return an evaluation_monitor_summary from *path*.

    Parameters
    ----------
    path:
        Path to an evaluation_monitor_summary JSON file.

    Returns
    -------
    dict
        The parsed summary.

    Raises
    ------
    EvaluationBudgetGovernorError
        If the file is missing or cannot be parsed.
    InvalidSummaryError
        If the loaded JSON fails schema validation.
    """
    path = Path(path)
    if not path.is_file():
        raise EvaluationBudgetGovernorError(
            f"evaluation_monitor_summary file not found: {path}"
        )
    try:
        with path.open(encoding="utf-8") as fh:
            summary = json.load(fh)
    except json.JSONDecodeError as exc:
        raise EvaluationBudgetGovernorError(
            f"Failed to parse evaluation_monitor_summary JSON at '{path}': {exc}"
        ) from exc

    validation_errors = validate_summary(summary)
    if validation_errors:
        raise InvalidSummaryError(
            "evaluation_monitor_summary failed schema validation: "
            + "; ".join(validation_errors)
        )

    logger.info("Loaded evaluation_monitor_summary summary_id=%s", summary.get("summary_id"))
    return summary


def validate_summary(summary: Any) -> List[str]:
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


def validate_decision(decision: Any) -> List[str]:
    """Validate *decision* against the evaluation_budget_decision JSON Schema.

    Parameters
    ----------
    decision:
        Object to validate.

    Returns
    -------
    list[str]
        Validation error messages. Empty list means the decision is valid.
    """
    schema = _load_schema(_BUDGET_DECISION_SCHEMA_PATH)
    return _validate_against_schema(decision, schema)


# ---------------------------------------------------------------------------
# Public API — policy engine
# ---------------------------------------------------------------------------


def evaluate_budget_status(
    summary: Dict[str, Any],
    thresholds: Optional[Dict[str, Any]] = None,
) -> Tuple[str, List[str], List[str]]:
    """Derive the budget status from a validated monitor summary.

    Uses multiple signals (drift_rate, failure_rate, burn_rate, trend) in
    combination to produce a deterministic classification.

    Parameters
    ----------
    summary:
        A schema-validated evaluation_monitor_summary dict.
    thresholds:
        Optional threshold overrides. Any key from ``_DEFAULT_THRESHOLDS``
        may be overridden.

    Returns
    -------
    tuple[str, list[str], list[str]]
        ``(status, reasons, triggered_thresholds)`` where *status* is one of
        ``"healthy" | "warning" | "exhausted" | "blocked"``.
    """
    t: Dict[str, Any] = dict(_DEFAULT_THRESHOLDS)
    if thresholds:
        t.update(thresholds)

    aggregates = summary["aggregates"]
    trend_analysis = summary["trend_analysis"]
    burn_rate = summary["burn_rate_assessment"]
    window = summary["window"]

    avg_drift_rate: float = aggregates["average_drift_rate"]
    total_failed_runs: int = aggregates["total_failed_runs"]
    total_critical_alerts: int = aggregates["total_critical_alerts"]
    total_runs: int = window["total_runs"]
    failure_rate: float = _safe_divide(total_failed_runs, total_runs)
    burn_status: str = burn_rate["status"]
    pass_rate_trend: str = trend_analysis["pass_rate_trend"]
    drift_rate_trend: str = trend_analysis["drift_rate_trend"]

    reasons: List[str] = []
    triggered: List[str] = []

    # --- Blocked signals (any one is sufficient for blocked) ---
    is_blocked = False

    if total_critical_alerts > 0 and failure_rate >= t["failure_rate_critical"]:
        is_blocked = True
        reasons.append(
            f"Critical alerts ({total_critical_alerts}) combined with critical "
            f"failure rate ({failure_rate:.0%} ≥ {t['failure_rate_critical']:.0%})"
        )
        triggered.append("critical_alerts_with_critical_failure_rate")

    if avg_drift_rate >= t["drift_rate_critical"] and failure_rate >= t["failure_rate_critical"]:
        is_blocked = True
        reasons.append(
            f"Critical drift rate ({avg_drift_rate:.0%} ≥ "
            f"{t['drift_rate_critical']:.0%}) combined with critical "
            f"failure rate ({failure_rate:.0%} ≥ {t['failure_rate_critical']:.0%})"
        )
        triggered.append("critical_drift_rate_with_critical_failure_rate")

    if is_blocked:
        return "blocked", reasons, triggered

    # --- Exhausted signals ---
    is_exhausted = False

    if t["burn_rate_exhausting_triggers_exhausted"] and burn_status == "exhausting":
        is_exhausted = True
        reasons.append(
            f"Burn rate is exhausting: "
            + "; ".join(burn_rate.get("reasons", ["burn rate exhausting"]))
        )
        triggered.append("burn_rate_exhausting")

    if total_critical_alerts > 0 and pass_rate_trend == "degrading":
        is_exhausted = True
        reasons.append(
            f"Critical alerts ({total_critical_alerts}) with degrading pass rate trend"
        )
        triggered.append("critical_alerts_with_degrading_trend")

    if is_exhausted:
        return "exhausted", reasons, triggered

    # --- Warning signals ---
    is_warning = False

    if avg_drift_rate >= t["drift_rate_warning"]:
        is_warning = True
        reasons.append(
            f"Drift rate ({avg_drift_rate:.0%}) ≥ warning threshold "
            f"({t['drift_rate_warning']:.0%})"
        )
        triggered.append("drift_rate_warning")

    if failure_rate >= t["failure_rate_warning"]:
        is_warning = True
        reasons.append(
            f"Failure rate ({failure_rate:.0%}) ≥ warning threshold "
            f"({t['failure_rate_warning']:.0%})"
        )
        triggered.append("failure_rate_warning")

    if t["burn_rate_elevated_triggers_warning"] and burn_status == "elevated":
        is_warning = True
        reasons.append(
            f"Burn rate is elevated: "
            + "; ".join(burn_rate.get("reasons", ["burn rate elevated"]))
        )
        triggered.append("burn_rate_elevated")

    if t["degrading_trend_triggers_warning"] and (
        pass_rate_trend == "degrading" or drift_rate_trend == "degrading"
    ):
        is_warning = True
        trends = []
        if pass_rate_trend == "degrading":
            trends.append("pass_rate")
        if drift_rate_trend == "degrading":
            trends.append("drift_rate")
        reasons.append(f"Degrading trend(s) detected: {', '.join(trends)}")
        triggered.append("degrading_trend")

    if total_critical_alerts > 0:
        is_warning = True
        reasons.append(f"One or more critical alerts recorded ({total_critical_alerts})")
        triggered.append("critical_alerts")

    if is_warning:
        return "warning", reasons, triggered

    # --- Healthy ---
    reasons.append("All signals within acceptable thresholds.")
    return "healthy", reasons, triggered


def determine_system_response(
    status: str,
    triggered_thresholds: List[str],
    thresholds: Optional[Dict[str, Any]] = None,
) -> str:
    """Map status to response via the canonical control-loop mapping.

    ``triggered_thresholds`` and ``thresholds`` are accepted for compatibility
    but do not affect mapping; status is the only input to preserve determinism.
    """
    del triggered_thresholds
    del thresholds
    _, response = map_control_loop_status_to_response(status)
    return response




def translate_to_legacy_response(control_loop_response: str) -> str:
    """Translate canonical control-loop response to legacy dialect."""
    translation = {
        "allow": "allow",
        "warn": "allow_with_warning",
        "freeze": "freeze_changes",
        "block": "block_release",
    }
    return translation.get(control_loop_response, "block_release")


def _build_required_actions(
    status: str,
    system_response: str,
    triggered_thresholds: List[str],
) -> List[str]:
    """Derive the set of required actions for a decision."""
    actions: List[str] = []

    if system_response == "allow":
        actions.append("No immediate action required. Continue monitoring.")
        return actions

    if system_response == "allow_with_warning":
        actions.append("Review warning signals before the next release.")
        if "drift_rate_warning" in triggered_thresholds:
            actions.append("Investigate elevated drift rate in recent runs.")
        if "failure_rate_warning" in triggered_thresholds:
            actions.append("Investigate increased failure rate in recent runs.")
        if "burn_rate_elevated" in triggered_thresholds:
            actions.append("Assess error budget consumption rate.")
        if "degrading_trend" in triggered_thresholds:
            actions.append("Review degrading SLI trends for root causes.")
        return actions

    if system_response == "freeze_changes":
        actions.append("Freeze all system changes until budget is restored.")
        actions.append("Conduct root-cause analysis of contributing signals.")
        if "burn_rate_exhausting" in triggered_thresholds:
            actions.append("Error budget exhausted — halt new feature deployment.")
        return actions

    if system_response == "require_review":
        actions.append("Halt automated deployments until human review is complete.")
        actions.append("Escalate to on-call engineer for immediate review.")
        actions.append("Review all triggered thresholds and recent run results.")
        return actions

    if system_response == "block_release":
        actions.append("Block all release activity immediately.")
        actions.append("Escalate to engineering leadership.")
        actions.append("Conduct mandatory post-mortem before any release.")
        return actions

    actions.append("Consult engineering team for guidance.")
    return actions


def build_decision_artifact(
    summary_id: str,
    status: str,
    system_response: str,
    reasons: List[str],
    triggered_thresholds: List[str],
    required_actions: List[str],
) -> Dict[str, Any]:
    """Assemble and schema-validate a ``evaluation_budget_decision`` artifact.

    Parameters
    ----------
    summary_id:
        ``summary_id`` of the source evaluation_monitor_summary.
    status:
        Budget health status.
    system_response:
        Governed system action.
    reasons:
        Human-readable explanation list.
    triggered_thresholds:
        List of threshold names that fired.
    required_actions:
        Actions that must be taken.

    Returns
    -------
    dict
        Schema-validated evaluation_budget_decision artifact.

    Raises
    ------
    EvaluationBudgetGovernorError
        If the produced artifact fails schema validation.
    """
    decision: Dict[str, Any] = {
        "decision_dialect": "legacy",
        "decision_id": _new_id(),
        "summary_id": summary_id,
        "status": status,
        "system_response": system_response,
        "reasons": reasons,
        "triggered_thresholds": triggered_thresholds,
        "required_actions": required_actions,
        "created_at": _now_iso(),
    }

    errors = validate_decision(decision)
    if errors:
        raise EvaluationBudgetGovernorError(
            "Produced budget decision failed schema validation: "
            + "; ".join(errors)
        )

    logger.info(
        "Budget decision built summary_id=%s status=%s system_response=%s",
        summary_id,
        status,
        system_response,
    )
    return decision


# ---------------------------------------------------------------------------
# Public API — batch entry point
# ---------------------------------------------------------------------------


def run_budget_governor(
    path: str | Path,
    thresholds: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Load a monitor summary from *path* and produce a governed decision.

    This is the primary entry point.  It is fail-closed: any invalid or
    missing input raises an exception rather than returning a partial result.

    Parameters
    ----------
    path:
        Path to an evaluation_monitor_summary JSON file.
    thresholds:
        Optional policy threshold overrides.

    Returns
    -------
    dict
        Schema-validated evaluation_budget_decision artifact.

    Raises
    ------
    EvaluationBudgetGovernorError
        If the file is missing, cannot be parsed, or the produced decision
        fails schema validation.
    InvalidSummaryError
        If the loaded summary fails schema validation.
    """
    summary = load_monitor_summary(path)

    status, reasons, triggered = evaluate_budget_status(summary, thresholds)
    canonical_response = determine_system_response(status, triggered, thresholds)
    legacy_response = translate_to_legacy_response(canonical_response)
    required_actions = _build_required_actions(status, legacy_response, triggered)

    decision = build_decision_artifact(
        summary_id=summary["summary_id"],
        status=status,
        system_response=legacy_response,
        reasons=reasons,
        triggered_thresholds=triggered,
        required_actions=required_actions,
    )

    logger.info(
        "Budget governor complete summary_id=%s status=%s canonical_response=%s legacy_response=%s",
        summary["summary_id"],
        status,
        canonical_response,
        legacy_response,
    )
    return decision


def build_validation_budget_decision(
    monitor_summary: Dict[str, Any],
) -> Dict[str, Any]:
    """Build an enforcement-ready control-loop budget decision.

    Converts control-loop ``evaluation_monitor_summary`` artifacts into
    control-loop ``evaluation_budget_decision`` artifacts.
    """
    summary_errors = validate_summary(monitor_summary)
    triggered_by_status: Dict[str, List[str]] = {
        "blocked": [],
        "exhausted": [],
        "warning": [],
    }
    reason_map: Dict[str, str] = {}

    if summary_errors:
        trigger = "malformed_monitor_summary"
        triggered_by_status["blocked"].append(trigger)
        reason_map[trigger] = "Monitor summary failed schema validation; fail-closed to blocked."
    else:
        raw_status = str(monitor_summary.get("overall_status") or "")
        aggregated = monitor_summary.get("aggregated_slis") if isinstance(monitor_summary.get("aggregated_slis"), dict) else {}

        if raw_status == "indeterminate":
            trigger = "indeterminate_monitor_state"
            triggered_by_status["blocked"].append(trigger)
            reason_map[trigger] = "Monitor summary status is indeterminate; fail-closed to blocked."
        elif raw_status == "blocked":
            trigger = "summary_reported_blocked"
            triggered_by_status["blocked"].append(trigger)
            reason_map[trigger] = "Monitor summary reported blocked status."
        elif raw_status == "exhausted":
            trigger = "summary_reported_exhausted"
            triggered_by_status["exhausted"].append(trigger)
            reason_map[trigger] = "Monitor summary reported exhausted status."
        elif raw_status == "warning":
            trigger = "summary_reported_warning"
            triggered_by_status["warning"].append(trigger)
            reason_map[trigger] = "Monitor summary reported warning status."
        elif raw_status == "healthy":
            pass
        else:
            trigger = "unknown_monitor_status"
            triggered_by_status["blocked"].append(trigger)
            reason_map[trigger] = "Monitor summary status missing or unrecognized; fail-closed to blocked."

        output_paths_rate = aggregated.get("output_paths_valid_rate")
        if not isinstance(output_paths_rate, (int, float)):
            trigger = "invalid_output_paths_valid_rate"
            triggered_by_status["blocked"].append(trigger)
            reason_map[trigger] = "output_paths_valid_rate missing or non-numeric; fail-closed to blocked."
        elif float(output_paths_rate) < 1.0:
            trigger = "output_paths_valid_rate_below_threshold"
            triggered_by_status["blocked"].append(trigger)
            reason_map[trigger] = "output_paths_valid_rate below 1.0 requires blocked response."

    if triggered_by_status["blocked"]:
        status = "blocked"
    elif triggered_by_status["exhausted"]:
        status = "exhausted"
    elif triggered_by_status["warning"]:
        status = "warning"
    else:
        status = "healthy"
    status, system_response = map_control_loop_status_to_response(status)

    triggered_thresholds = (
        sorted(set(triggered_by_status["blocked"]))
        if status == "blocked"
        else sorted(set(triggered_by_status["exhausted"]))
        if status == "exhausted"
        else sorted(set(triggered_by_status["warning"]))
    )
    reasons = [reason_map[trigger] for trigger in triggered_thresholds]
    if status == "healthy":
        reasons = ["All monitored thresholds are healthy."]

    decision = {
        "decision_dialect": "control_loop",
        "decision_id": _deterministic_control_decision_id(monitor_summary, status, triggered_thresholds),
        "summary_id": str(monitor_summary.get("summary_id") or "unknown-summary"),
        "trace_id": str(monitor_summary.get("trace_id") or "unknown-trace"),
        "timestamp": _canonical_timestamp(monitor_summary.get("generated_at")),
        "status": status,
        "system_response": system_response,
        "triggered_thresholds": triggered_thresholds,
        "reasons": reasons,
    }

    decision_errors = validate_decision(decision)
    if decision_errors:
        raise EvaluationBudgetGovernorError(
            "Produced control-loop budget decision failed schema validation: "
            + "; ".join(decision_errors)
        )
    return decision

def run_validation_control_loop(bundle_path: str | Path) -> Dict[str, Any]:
    """Canonical control-loop adapter for bundle→budget decision."""
    from spectrum_systems.modules.runtime.evaluation_monitor import (
        build_validation_monitor_record,
        summarize_validation_monitor_records,
    )
    from spectrum_systems.modules.runtime.run_bundle_validator import validate_and_emit_decision

    decision = validate_and_emit_decision(bundle_path)
    record = build_validation_monitor_record(decision)
    summary = summarize_validation_monitor_records([record])
    return build_validation_budget_decision(summary)

