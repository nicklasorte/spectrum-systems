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
from spectrum_systems.modules.runtime.provenance_verification import (
    ProvenanceVerificationError,
    validate_required_identity,
)

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
    if not isinstance(error_budget.get("objectives"), list) or not error_budget["objectives"]:
        raise EvaluationControlError("replay_result.error_budget_status.objectives must be present and non-empty")
    for objective in error_budget["objectives"]:
        if not isinstance(objective, dict):
            raise EvaluationControlError("replay_result.error_budget_status.objectives entries must be objects")
        for field in ("consumed_error", "remaining_error", "consumption_ratio", "status"):
            if field not in objective:
                raise EvaluationControlError(
                    f"replay_result.error_budget_status.objectives entry missing required field: {field}"
                )

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
    replay_run_id = replay_result.get("replay_run_id")
    try:
        validate_required_identity(
            {"run_id": replay_run_id, "trace_id": trace_id},
            label="replay_result",
        )
    except ProvenanceVerificationError as exc:
        raise EvaluationControlError(str(exc)) from exc

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
        if decision_label == "deny":
            return system_status, system_response, decision_label, rationale_code
        if decision_label == "allow":
            return "warning", "warn", "require_review", "require_review_budget_warning"
        return system_status, system_response, "require_review", rationale_code

    if budget_status == "exhausted":
        if "budget_exhausted" not in triggered_signals:
            triggered_signals.append("budget_exhausted")
        if "trust_breach" in triggered_signals or "indeterminate_failure" in triggered_signals:
            return "blocked", "block", "deny", "deny_budget_exhausted"
        return "exhausted", "freeze", "deny", "deny_budget_exhausted"

    if "budget_invalid" not in triggered_signals:
        triggered_signals.append("budget_invalid")
    return "blocked", "block", "deny", "deny_budget_invalid"


def _enforce_budget_authority(*, budget_status: str, system_response: str, decision_label: str) -> None:
    if budget_status == "exhausted" and system_response not in {"freeze", "block"}:
        raise EvaluationControlError(
            "BUDGET_ENFORCEMENT_MISSING: exhausted budget must produce freeze or block response"
        )
    if budget_status == "warning" and system_response == "allow":
        raise EvaluationControlError(
            "BUDGET_ENFORCEMENT_MISSING: warning budget must not produce allow response"
        )
    if budget_status in {"exhausted", "invalid"} and decision_label != "deny":
        raise EvaluationControlError(
            "BUDGET_ENFORCEMENT_MISSING: exhausted/invalid budget must produce deny decision"
        )




def _resolve_governed_thresholds(thresholds: Optional[Dict[str, float]]) -> Dict[str, float]:
    resolved = dict(DEFAULT_THRESHOLDS)
    if not thresholds:
        return resolved

    for key, value in thresholds.items():
        if key not in DEFAULT_THRESHOLDS:
            raise EvaluationControlError(f"threshold override contains unknown key: {key}")
        if not isinstance(value, (int, float)):
            raise EvaluationControlError(f"threshold override for {key} must be numeric")

    candidate = dict(resolved)
    candidate.update({k: float(v) for k, v in thresholds.items()})

    if candidate["reliability_threshold"] < DEFAULT_THRESHOLDS["reliability_threshold"]:
        raise EvaluationControlError("threshold override cannot relax reliability_threshold below governed default")
    if candidate["trust_threshold"] < DEFAULT_THRESHOLDS["trust_threshold"]:
        raise EvaluationControlError("threshold override cannot relax trust_threshold below governed default")
    if candidate["drift_threshold"] > DEFAULT_THRESHOLDS["drift_threshold"]:
        raise EvaluationControlError("threshold override cannot relax drift_threshold above governed default")

    return candidate

def _resolve_recurrence_prevention_binding(
    signal_artifact: Dict[str, Any],
    failure_policy_binding: Dict[str, Any],
) -> tuple[Dict[str, Any], Dict[str, Any], int]:
    required_binding = (
        "eval_case_id",
        "failure_id",
        "trace_id",
        "policy_id",
        "trigger_condition",
        "control_decision_surface",
        "failure_class_id",
        "prevention_action",
        "prevention_rule_id",
        "recurrence_scope",
        "recurrence_prevention_artifact",
    )
    for field in required_binding:
        value = failure_policy_binding.get(field)
        if value in (None, ""):
            raise EvaluationControlError(f"failure_policy_binding missing required field: {field}")

    if failure_policy_binding["eval_case_id"] != signal_artifact.get("eval_case_id"):
        raise EvaluationControlError("failure_policy_binding.eval_case_id must match failure_eval_case.eval_case_id")
    if failure_policy_binding["trace_id"] != signal_artifact.get("trace_id"):
        raise EvaluationControlError("failure_policy_binding.trace_id must match failure_eval_case.trace_id")
    if failure_policy_binding["failure_id"] != signal_artifact.get("source_artifact_id"):
        raise EvaluationControlError("failure_policy_binding.failure_id must match failure_eval_case.source_artifact_id")
    if failure_policy_binding["control_decision_surface"] != "evaluation_control_decision":
        raise EvaluationControlError("failure_policy_binding.control_decision_surface must target evaluation_control_decision")
    if failure_policy_binding["failure_class_id"] != signal_artifact.get("failure_class"):
        raise EvaluationControlError("failure_policy_binding.failure_class_id must match failure_eval_case.failure_class")

    recurrence_scope = failure_policy_binding.get("recurrence_scope")
    if not isinstance(recurrence_scope, dict):
        raise EvaluationControlError("failure_policy_binding.recurrence_scope must be an object")
    required_scope_fields = ("failure_class_id", "failure_stage", "runtime_environment")
    for field in required_scope_fields:
        value = recurrence_scope.get(field)
        if not isinstance(value, str) or not value.strip() or value.strip() in {"*", "any", "unknown"}:
            raise EvaluationControlError(f"ambiguous recurrence scope for field '{field}'")

    normalized_inputs = signal_artifact.get("normalized_inputs")
    if not isinstance(normalized_inputs, dict):
        raise EvaluationControlError("failure_eval_case.normalized_inputs must be an object")
    if recurrence_scope["failure_class_id"] != str(signal_artifact.get("failure_class") or ""):
        raise EvaluationControlError("ambiguous recurrence scope for field 'failure_class_id'")
    if recurrence_scope["failure_stage"] != str(signal_artifact.get("failure_stage") or ""):
        raise EvaluationControlError("ambiguous recurrence scope for field 'failure_stage'")
    runtime_environment = str(normalized_inputs.get("runtime_environment") or "")
    if recurrence_scope["runtime_environment"] != runtime_environment:
        raise EvaluationControlError("ambiguous recurrence scope for field 'runtime_environment'")

    prevention_artifact = failure_policy_binding.get("recurrence_prevention_artifact")
    if not isinstance(prevention_artifact, dict):
        raise EvaluationControlError("failure_policy_binding.recurrence_prevention_artifact must be an object")
    for field in ("artifact_id", "source_failure_class_id", "linked_eval_case_ids", "prevention_rule_id", "prevention_action"):
        value = prevention_artifact.get(field)
        if value in (None, ""):
            raise EvaluationControlError(f"recurrence prevention artifact missing required field: {field}")
    if prevention_artifact["prevention_rule_id"] != failure_policy_binding["prevention_rule_id"]:
        raise EvaluationControlError("recurrence prevention artifact rule linkage mismatch")
    if prevention_artifact["prevention_action"] != failure_policy_binding["prevention_action"]:
        raise EvaluationControlError("recurrence prevention artifact action linkage mismatch")

    recurrence_count = failure_policy_binding.get("recurrence_count", 1)
    if not isinstance(recurrence_count, int) or recurrence_count < 1:
        raise EvaluationControlError("failure_policy_binding.recurrence_count must be an integer >= 1")
    return recurrence_scope, prevention_artifact, recurrence_count


def build_evaluation_control_decision(
    signal_artifact: Dict[str, Any],
    *,
    thresholds: Optional[Dict[str, float]] = None,
    failure_policy_binding: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a deterministic evaluation_control_decision from governed signal artifacts."""
    t = _resolve_governed_thresholds(thresholds)
    seeded_signals: List[str] = []
    artifact_type = signal_artifact.get("artifact_type") if isinstance(signal_artifact, dict) else None
    if artifact_type == "replay_result":
        eval_summary = _to_eval_summary_from_replay_result(signal_artifact)
        source_artifact_id = signal_artifact["replay_id"]
        created_at = _canonical_timestamp(eval_summary.get("created_at"))
        signal_type = "eval_summary"
    elif artifact_type == "cross_run_intelligence_decision":
        trace_ids = signal_artifact.get("trace_ids")
        if not isinstance(trace_ids, list) or not trace_ids or not isinstance(trace_ids[0], str) or not trace_ids[0]:
            raise EvaluationControlError("cross_run_intelligence_decision.trace_ids must include at least one trace_id")
        signal_map = {"stable": "healthy", "warning": "warning", "unstable": "blocked"}
        mapped_status = signal_map.get(str(signal_artifact.get("system_signal") or ""))
        if mapped_status is None:
            raise EvaluationControlError("cross_run_intelligence_decision.system_signal must be stable|warning|unstable")
        eval_summary = {
            "artifact_type": "eval_summary",
            "schema_version": "1.0.0",
            "trace_id": trace_ids[0],
            "eval_run_id": str(signal_artifact.get("intelligence_id") or "xrun-unknown"),
            "pass_rate": 1.0 if mapped_status == "healthy" else 0.8 if mapped_status == "warning" else 0.4,
            "drift_rate": 0.0 if mapped_status == "healthy" else 0.3 if mapped_status == "warning" else 0.8,
            "reproducibility_score": 1.0 if mapped_status == "healthy" else 0.7 if mapped_status == "warning" else 0.3,
            "indeterminate_failure_count": 0,
            "created_at": _canonical_timestamp(signal_artifact.get("timestamp")),
            "budget_status": "healthy" if mapped_status == "healthy" else "warning" if mapped_status == "warning" else "exhausted",
        }
        source_artifact_id = str(signal_artifact.get("intelligence_id") or "unknown")
        created_at = _canonical_timestamp(eval_summary.get("created_at"))
        signal_type = "failure_eval_case"
    elif artifact_type == "eval_summary":
        raise EvaluationControlError(
            "RUNTIME_REPLAY_BOUNDARY_VIOLATION: eval_summary is not permitted in runtime seams; replay_result is required"
        )
    elif artifact_type == "failure_eval_case":
        failure_schema = load_schema("failure_eval_case")
        failure_errors = _validate(signal_artifact, failure_schema)
        if failure_errors:
            raise EvaluationControlError("failure_eval_case failed validation: " + "; ".join(failure_errors))
        if not isinstance(failure_policy_binding, dict):
            raise EvaluationControlError("failure_eval_case requires deterministic failure_policy_binding")
        _, _, recurrence_count = _resolve_recurrence_prevention_binding(
            signal_artifact,
            failure_policy_binding,
        )

        classification_map = {
            "runtime_failure": ("blocked", "block", ["trust_breach", "stability_breach"], "deny_failure_eval_case"),
            "review_boundary_halt": ("warning", "warn", ["indeterminate_failure"], "require_review_warning_signal"),
            "control_indeterminate": ("blocked", "block", ["indeterminate_failure", "trust_breach"], "deny_failure_eval_case"),
        }
        failure_class = str(signal_artifact.get("failure_class") or "")
        if failure_class not in classification_map:
            raise EvaluationControlError("failure_eval_case.failure_class must be runtime_failure|review_boundary_halt|control_indeterminate")
        system_status, system_response, seeded_signals, rationale_code = classification_map[failure_class]
        seeded_signals = list(seeded_signals)
        if recurrence_count >= 2 and system_response == "warn":
            system_status, system_response, rationale_code = "blocked", "block", "deny_repeat_failure_escalation"
        if recurrence_count >= 2 and system_response != "warn":
            rationale_code = "deny_repeat_failure_escalation"
        if recurrence_count >= 3:
            system_status, system_response, rationale_code = "blocked", "block", "deny_repeat_failure_escalation"
        eval_case_id = str(signal_artifact.get("eval_case_id") or "")
        created_at = _canonical_timestamp(signal_artifact.get("created_at"))
        eval_summary = {
            "artifact_type": "eval_summary",
            "schema_version": "1.0.0",
            "trace_id": str(signal_artifact.get("trace_id") or ""),
            "eval_run_id": eval_case_id,
            "pass_rate": 0.0,
            "drift_rate": 1.0 if failure_class != "review_boundary_halt" else 0.3,
            "reproducibility_score": 0.0 if failure_class != "review_boundary_halt" else 0.5,
            "indeterminate_failure_count": 1 if failure_class != "runtime_failure" else 0,
            "created_at": created_at,
            "budget_status": "exhausted",
        }
        source_artifact_id = eval_case_id
        signal_type = "failure_eval_case"
    else:
        raise EvaluationControlError(
            "signal_artifact must be replay_result, cross_run_intelligence_decision, or failure_eval_case"
        )

    pass_rate = float(eval_summary["pass_rate"])
    drift_rate = float(eval_summary["drift_rate"])
    reproducibility = float(eval_summary["reproducibility_score"])
    indeterminate_failures = _extract_indeterminate_failure_count(eval_summary)

    triggered_signals: List[str] = list(seeded_signals if artifact_type == "failure_eval_case" else [])
    if pass_rate < t["reliability_threshold"]:
        triggered_signals.append("reliability_breach")
    if drift_rate > t["drift_threshold"]:
        triggered_signals.append("stability_breach")
    if reproducibility < t["trust_threshold"]:
        triggered_signals.append("trust_breach")
    if indeterminate_failures > 0:
        triggered_signals.append("indeterminate_failure")
    triggered_signals = list(dict.fromkeys(triggered_signals))

    severe_hits = [s for s in triggered_signals if s in SEVERE_SIGNALS]
    if artifact_type == "failure_eval_case":
        pass
    else:
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
    if artifact_type != "failure_eval_case":
        budget_status = str(eval_summary.get("budget_status") or "invalid")
        system_status, system_response, decision_label, rationale_code = _apply_budget_status_override(
            budget_status=budget_status,
            triggered_signals=triggered_signals,
            system_status=system_status,
            system_response=system_response,
            decision_label=decision_label,
            rationale_code=rationale_code,
        )
        _enforce_budget_authority(
            budget_status=budget_status,
            system_response=system_response,
            decision_label=decision_label,
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
            "signal_type": signal_type,
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
