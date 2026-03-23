"""Evaluation → Control Decision Mapper (BBA).

Consumes ``eval_summary`` artifacts and emits deterministic,
schema-governed ``evaluation_control_decision`` artifacts.

Design rules
------------
- Fail closed: malformed/missing input never yields ``allow``.
- Deterministic: threshold-based signal mapping only.
- No autonomy: no heuristic overrides or free-form policy reasoning.
- Governed output: every emitted decision validates against
  ``evaluation_control_decision.schema.json``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCHEMA_DIR = _REPO_ROOT / "contracts" / "schemas"
_DECISION_SCHEMA_PATH = _SCHEMA_DIR / "evaluation_control_decision.schema.json"

DEFAULT_THRESHOLDS: Dict[str, float] = {
    "reliability_threshold": 0.85,
    "drift_threshold": 0.20,
    "trust_threshold": 0.80,
}

SEVERE_SIGNALS = frozenset({"stability_breach", "trust_breach", "indeterminate_failure"})
STATUS_RESPONSE_MAP: Dict[str, str] = {
    "healthy": "allow",
    "warning": "warn",
    "exhausted": "freeze",
    "blocked": "block",
}


class EvaluationControlError(Exception):
    """Raised for any evaluation control mapping failure."""


def _canonical_timestamp(value: Any) -> str:
    if isinstance(value, str) and value:
        return value
    return "1970-01-01T00:00:00Z"


def _deterministic_decision_id(
    *,
    eval_run_id: str,
    triggered_signals: List[str],
    schema_version: str,
) -> str:
    signal_seed = ",".join(triggered_signals)
    seed = f"{eval_run_id}|{signal_seed}|{schema_version}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12].upper()
    return f"ECD-{digest}"




def map_control_loop_status_to_response(status: Any) -> tuple[str, str]:
    """Canonical control-loop status→response mapping.

    This is the single runtime authority for mapping:
    healthy→allow, warning→warn, exhausted→freeze, blocked→block.
    Unknown status values fail-closed to blocked/block.
    """
    status_text = str(status)
    if status_text not in STATUS_RESPONSE_MAP:
        status_text = "blocked"
    return status_text, STATUS_RESPONSE_MAP[status_text]


def map_status_to_response(status: Any) -> tuple[str, str]:
    """Backward-compatible alias for canonical control-loop mapping."""
    return map_control_loop_status_to_response(status)


def _load_decision_schema() -> Dict[str, Any]:
    return json.loads(_DECISION_SCHEMA_PATH.read_text(encoding="utf-8"))


def _validate(artifact: Any, schema: Dict[str, Any]) -> List[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(artifact), key=lambda e: list(e.absolute_path))
    return [e.message for e in errors]


def _extract_indeterminate_failure_count(summary: Dict[str, Any]) -> int:
    for key in ("indeterminate_failure_count", "indeterminate_count"):
        value = summary.get(key)
        if isinstance(value, int) and value > 0:
            return value
    return 0


def _fail_closed_decision(
    *,
    eval_run_id: str,
    trace_id: str,
    thresholds: Dict[str, float],
    signal: str,
) -> Dict[str, Any]:
    schema_version = "1.1.0"
    triggered_signals = [signal]
    rationale_code = (
        "deny_missing_required_signal"
        if signal == "missing_required_signal"
        else "deny_malformed_signal"
    )
    return {
        "artifact_type": "evaluation_control_decision",
        "schema_version": schema_version,
        "decision_id": _deterministic_decision_id(
            eval_run_id=eval_run_id,
            triggered_signals=triggered_signals,
            schema_version=schema_version,
        ),
        "eval_run_id": eval_run_id,
        "system_status": "blocked",
        "system_response": "block",
        "triggered_signals": triggered_signals,
        "threshold_snapshot": thresholds,
        "trace_id": trace_id,
        "created_at": "1970-01-01T00:00:00Z",
        "decision": "deny",
        "rationale_code": rationale_code,
        "input_signal_reference": {
            "signal_type": "eval_summary",
            "source_artifact_id": eval_run_id,
        },
        "run_id": eval_run_id,
    }


def _fallback_eval_run_id(eval_summary: Dict[str, Any]) -> str:
    eval_run_id = eval_summary.get("eval_run_id")
    if isinstance(eval_run_id, str) and eval_run_id.strip():
        return eval_run_id
    summary_seed = json.dumps(eval_summary, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(summary_seed.encode("utf-8")).hexdigest()[:12]
    return f"malformed-{digest}"


def build_evaluation_control_decision(
    eval_summary: Dict[str, Any],
    *,
    thresholds: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Build a deterministic evaluation_control_decision from an eval_summary.

    Fail-closed behavior:
    - malformed ``eval_summary`` -> blocked/block decision
    - missing required signals -> blocked/block decision
    """
    t = dict(DEFAULT_THRESHOLDS)
    if thresholds:
        t.update(thresholds)

    eval_schema = load_schema("eval_summary")
    if _validate(eval_summary, eval_schema):
        decision = _fail_closed_decision(
            eval_run_id=_fallback_eval_run_id(eval_summary),
            trace_id=str(eval_summary.get("trace_id") or "unknown-trace"),
            thresholds=t,
            signal="malformed_eval_summary",
        )
        decision_errors = _validate(decision, _load_decision_schema())
        if decision_errors:
            raise EvaluationControlError("; ".join(decision_errors))
        return decision

    required_signals = ("pass_rate", "drift_rate", "reproducibility_score")
    if any(signal not in eval_summary for signal in required_signals):
        decision = _fail_closed_decision(
            eval_run_id=_fallback_eval_run_id(eval_summary),
            trace_id=str(eval_summary.get("trace_id") or "unknown-trace"),
            thresholds=t,
            signal="missing_required_signal",
        )
        decision_errors = _validate(decision, _load_decision_schema())
        if decision_errors:
            raise EvaluationControlError("; ".join(decision_errors))
        return decision

    pass_rate = float(eval_summary["pass_rate"])
    drift_rate = float(eval_summary["drift_rate"])
    reproducibility = float(eval_summary["reproducibility_score"])
    indeterminate_failures = _extract_indeterminate_failure_count(eval_summary)

    triggered_signals: List[str] = []
    if pass_rate < t["reliability_threshold"]:
        triggered_signals.append("reliability_breach")
    if drift_rate > t["drift_threshold"]:
        triggered_signals.append("stability_breach")
    if reproducibility < t["trust_threshold"]:
        triggered_signals.append("trust_breach")
    if indeterminate_failures > 0:
        triggered_signals.append("indeterminate_failure")

    severe_hits = [s for s in triggered_signals if s in SEVERE_SIGNALS]

    if not triggered_signals:
        system_status = "healthy"
    elif "trust_breach" in triggered_signals or len(severe_hits) >= 2:
        system_status = "blocked"
    elif "stability_breach" in triggered_signals:
        system_status = "exhausted"
    else:
        system_status = "warning"
    system_status, system_response = map_control_loop_status_to_response(system_status)

    if system_response == "allow":
        decision_label = "allow"
        rationale_code = "allow_healthy_eval_summary"
    elif system_response == "warn":
        decision_label = "require_review"
        rationale_code = "require_review_warning_signal"
    elif "trust_breach" in triggered_signals:
        decision_label = "deny"
        rationale_code = "deny_trust_breach"
    elif "stability_breach" in triggered_signals:
        decision_label = "deny"
        rationale_code = "deny_stability_breach"
    elif "indeterminate_failure" in triggered_signals:
        decision_label = "deny"
        rationale_code = "deny_indeterminate_failure"
    else:
        decision_label = "deny"
        rationale_code = "deny_reliability_breach"

    schema_version = "1.1.0"
    decision = {
        "artifact_type": "evaluation_control_decision",
        "schema_version": schema_version,
        "decision_id": _deterministic_decision_id(
            eval_run_id=eval_summary["eval_run_id"],
            triggered_signals=triggered_signals,
            schema_version=schema_version,
        ),
        "eval_run_id": eval_summary["eval_run_id"],
        "system_status": system_status,
        "system_response": system_response,
        "triggered_signals": triggered_signals,
        "threshold_snapshot": {
            "reliability_threshold": t["reliability_threshold"],
            "drift_threshold": t["drift_threshold"],
            "trust_threshold": t["trust_threshold"],
        },
        "trace_id": eval_summary["trace_id"],
        "created_at": _canonical_timestamp(eval_summary.get("created_at")),
        "decision": decision_label,
        "rationale_code": rationale_code,
        "input_signal_reference": {
            "signal_type": "eval_summary",
            "source_artifact_id": eval_summary["eval_run_id"],
        },
        "run_id": eval_summary["eval_run_id"],
    }

    decision_errors = _validate(decision, _load_decision_schema())
    if decision_errors:
        raise EvaluationControlError(
            "evaluation_control_decision failed schema validation: " + "; ".join(decision_errors)
        )
    return decision
