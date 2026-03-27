"""Evaluation → Control Decision Mapper (BBA).

Consumes authoritative ``replay_result`` artifacts and emits deterministic,
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
STATUS_RESPONSE_MAP = {
    "healthy": "allow",
    "warning": "warn",
    "exhausted": "freeze",
    "blocked": "block",
}


class EvaluationControlError(Exception):
    """Raised for any evaluation control mapping failure."""


def _canonical_timestamp(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise EvaluationControlError("replay_result.timestamp must be a non-empty string")
    return value


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


def map_status_to_response(status: Any) -> tuple[str, str]:
    status_text = str(status)
    if status_text not in STATUS_RESPONSE_MAP:
        status_text = "blocked"
    return status_text, STATUS_RESPONSE_MAP[status_text]


def _load_decision_schema() -> Dict[str, Any]:
    return json.loads(_DECISION_SCHEMA_PATH.read_text(encoding="utf-8"))


def _validate(artifact: Any, schema: Dict[str, Any]) -> List[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(artifact), key=lambda e: list(e.absolute_path))
    return [e.message for e in errors]


def _extract_indeterminate_failure_count(summary: Dict[str, Any]) -> int:
    value = summary.get("indeterminate_failure_count")
    return value if isinstance(value, int) and value > 0 else 0


def _require_metric(metrics: Dict[str, Any], metric_name: str) -> float:
    value = metrics.get(metric_name)
    if not isinstance(value, (int, float)):
        raise EvaluationControlError(
            f"replay_result.observability_metrics.metrics.{metric_name} must be numeric"
        )
    return float(value)


def _optional_drift_rate(metrics: Dict[str, Any], *, drift_detected: bool) -> float:
    """Return drift metric when present, else deterministically derive from replay drift flag."""
    value = metrics.get("drift_exceed_threshold_rate")
    if value is None:
        return 1.0 if drift_detected else 0.0
    if not isinstance(value, (int, float)):
        raise EvaluationControlError(
            "replay_result.observability_metrics.metrics.drift_exceed_threshold_rate must be numeric when present"
        )
    return float(value)


def _to_eval_summary_from_replay_result(replay_result: Dict[str, Any]) -> Dict[str, Any]:
    replay_schema = load_schema("replay_result")
    errors = _validate(replay_result, replay_schema)
    if errors:
        raise EvaluationControlError("replay_result failed validation: " + "; ".join(errors))

    observability = replay_result.get("observability_metrics")
    if not isinstance(observability, dict):
        raise EvaluationControlError("replay_result must embed observability_metrics")
    error_budget = replay_result.get("error_budget_status")
    if not isinstance(error_budget, dict):
        raise EvaluationControlError("replay_result must embed error_budget_status")

    obs_errors = _validate(observability, load_schema("observability_metrics"))
    if obs_errors:
        raise EvaluationControlError("observability_metrics failed validation: " + "; ".join(obs_errors))
    budget_errors = _validate(error_budget, load_schema("error_budget_status"))
    if budget_errors:
        raise EvaluationControlError("error_budget_status failed validation: " + "; ".join(budget_errors))

    trace_id = replay_result.get("trace_id")
    if not isinstance(trace_id, str) or not trace_id:
        raise EvaluationControlError("replay_result.trace_id must be a non-empty string")
    if observability.get("trace_refs", {}).get("trace_id") != trace_id:
        raise EvaluationControlError("REPLAY_INVALID_TRACE_LINKAGE: observability_metrics trace mismatch")
    if error_budget.get("trace_refs", {}).get("trace_id") != trace_id:
        raise EvaluationControlError("REPLAY_INVALID_TRACE_LINKAGE: error_budget_status trace mismatch")
    if error_budget.get("observability_metrics_id") != observability.get("artifact_id"):
        raise EvaluationControlError(
            "REPLAY_INVALID_LINEAGE: error_budget_status.observability_metrics_id must reference embedded observability_metrics.artifact_id"
        )

    metrics = observability.get("metrics")
    if not isinstance(metrics, dict):
        raise EvaluationControlError("observability_metrics.metrics must be an object")
    drift_detected = replay_result.get("drift_detected")
    if not isinstance(drift_detected, bool):
        raise EvaluationControlError("replay_result.drift_detected must be boolean")
    consistency_status = replay_result.get("consistency_status")
    if consistency_status not in {"match", "mismatch", "indeterminate"}:
        raise EvaluationControlError("replay_result.consistency_status must be match|mismatch|indeterminate")
    reproducibility_score = {"match": 1.0, "mismatch": 0.0, "indeterminate": 0.5}[consistency_status]

    return {
        "artifact_type": "eval_summary",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "eval_run_id": replay_result.get("replay_run_id"),
        "pass_rate": _require_metric(metrics, "replay_success_rate"),
        "drift_rate": _optional_drift_rate(metrics, drift_detected=drift_detected),
        "reproducibility_score": reproducibility_score,
        "indeterminate_failure_count": 1 if consistency_status == "indeterminate" else 0,
        "created_at": _canonical_timestamp(replay_result.get("timestamp")),
        "budget_status": str(error_budget.get("budget_status") or "invalid"),
    }


def _apply_budget_status_override(
    *,
    budget_status: str,
    triggered_signals: List[str],
    system_status: str,
    system_response: str,
    decision_label: str,
    rationale_code: str,
) -> tuple[str, str, str, str]:
    if budget_status == "healthy":
        return system_status, system_response, decision_label, rationale_code

    if budget_status == "warning":
        if "budget_warning" not in triggered_signals:
            triggered_signals.append("budget_warning")
        return "warning", "warn", "require_review", "require_review_budget_warning"

    if budget_status == "exhausted":
        if "budget_exhausted" not in triggered_signals:
            triggered_signals.append("budget_exhausted")
        if "trust_breach" in triggered_signals or "indeterminate_failure" in triggered_signals:
            return "blocked", "block", "deny", "deny_budget_exhausted"
        return "exhausted", "freeze", "deny", "deny_budget_exhausted"

    if "budget_invalid" not in triggered_signals:
        triggered_signals.append("budget_invalid")
    return "blocked", "block", "deny", "deny_budget_invalid"


def build_evaluation_control_decision(
    signal_artifact: Dict[str, Any],
    *,
    thresholds: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Build a deterministic evaluation_control_decision from governed signal artifacts."""
    t = dict(DEFAULT_THRESHOLDS)
    if thresholds:
        t.update(thresholds)
    artifact_type = signal_artifact.get("artifact_type") if isinstance(signal_artifact, dict) else None
    if artifact_type == "replay_result":
        eval_summary = _to_eval_summary_from_replay_result(signal_artifact)
        source_artifact_id = signal_artifact["replay_id"]
        created_at = _canonical_timestamp(eval_summary.get("created_at"))
    elif artifact_type == "eval_summary":
        raise EvaluationControlError(
            "RUNTIME_REPLAY_BOUNDARY_VIOLATION: eval_summary is not permitted in runtime seams; replay_result is required"
        )
    else:
        raise EvaluationControlError("signal_artifact must be replay_result")

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
    system_status, system_response = map_status_to_response(system_status)

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
    else:
        decision_label = "deny"
        rationale_code = "deny_reliability_breach"
    budget_status = str(eval_summary.get("budget_status") or "invalid")
    system_status, system_response, decision_label, rationale_code = _apply_budget_status_override(
        budget_status=budget_status,
        triggered_signals=triggered_signals,
        system_status=system_status,
        system_response=system_response,
        decision_label=decision_label,
        rationale_code=rationale_code,
    )

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
        "created_at": created_at,
        "decision": decision_label,
        "rationale_code": rationale_code,
        "input_signal_reference": {
            "signal_type": "eval_summary",
            "source_artifact_id": source_artifact_id,
        },
        "run_id": eval_summary["eval_run_id"],
    }

    decision_errors = _validate(decision, _load_decision_schema())
    if decision_errors:
        raise EvaluationControlError(
            "evaluation_control_decision failed schema validation: " + "; ".join(decision_errors)
        )
    return decision
