"""Unified deterministic control-loop engine for governed signal inputs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.evaluation_control import (
    EvaluationControlError,
    build_evaluation_control_decision,
)
from spectrum_systems.modules.runtime.judgment_learning import evaluate_judgment_drift_threshold_policy
from spectrum_systems.modules.runtime.judgment_enforcement import (
    build_judgment_enforcement_artifacts,
)


class ControlLoopError(Exception):
    """Raised when control-loop evaluation cannot produce a governed decision."""


_ERROR_BUDGET_SEVERITY_ORDER = {
    "healthy": 0,
    "warning": 1,
    "exhausted": 2,
    "invalid": 3,
}
_MAX_EMBEDDED_TIMESTAMP_DELTA_SECONDS = 366 * 24 * 60 * 60
_OBSERVABILITY_BUDGET_TOLERANCE = 1e-6


def _validate(instance: Any, schema: Dict[str, Any]) -> List[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    return [e.message for e in errors]


def _parse_rfc3339_utc(value: Any, *, field_name: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ControlLoopError(f"{field_name} must be a non-empty RFC3339 timestamp string")
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ControlLoopError(f"{field_name} must be a valid RFC3339 timestamp string") from exc
    if parsed.tzinfo is None:
        raise ControlLoopError(f"{field_name} must include timezone information")
    return parsed


def aggregate_error_budget_window(
    replay_results: List[Dict[str, Any]],
    *,
    last_n_runs: int = 5,
) -> Dict[str, Any]:
    """Thin deterministic rolling-window aggregation for replay error-budget statuses."""
    if not isinstance(last_n_runs, int) or last_n_runs <= 0:
        raise ControlLoopError("last_n_runs must be a positive integer")
    if not isinstance(replay_results, list):
        raise ControlLoopError("replay_results must be a list")

    normalized_rows: List[Dict[str, Any]] = []
    budget_schema = load_schema("error_budget_status")
    for row in replay_results:
        if not isinstance(row, dict):
            raise ControlLoopError("each replay result in replay_results must be a dict")
        replay_run_id = row.get("replay_run_id")
        if not isinstance(replay_run_id, str) or not replay_run_id.strip():
            raise ControlLoopError("each replay result must include replay_run_id")
        budget = row.get("error_budget_status")
        if not isinstance(budget, dict):
            raise ControlLoopError("each replay result must include error_budget_status")
        budget_errors = _validate(budget, budget_schema)
        if budget_errors:
            raise ControlLoopError("error_budget_status failed validation: " + "; ".join(budget_errors))
        budget_status = budget.get("budget_status")
        if budget_status not in _ERROR_BUDGET_SEVERITY_ORDER:
            raise ControlLoopError("each error_budget_status.budget_status must be healthy|warning|exhausted|invalid")
        timestamp = str(row.get("timestamp") or "")
        normalized_rows.append(
            {
                "replay_run_id": replay_run_id,
                "budget_status": budget_status,
                "timestamp": timestamp,
            }
        )

    sorted_rows = sorted(normalized_rows, key=lambda item: (item["timestamp"], item["replay_run_id"]))
    window = sorted_rows[-last_n_runs:]
    counts = {key: 0 for key in _ERROR_BUDGET_SEVERITY_ORDER}
    for row in window:
        counts[row["budget_status"]] += 1
    aggregate_status = "healthy"
    for row in window:
        if _ERROR_BUDGET_SEVERITY_ORDER[row["budget_status"]] > _ERROR_BUDGET_SEVERITY_ORDER[aggregate_status]:
            aggregate_status = row["budget_status"]
    return {
        "window_size": len(window),
        "requested_window_size": last_n_runs,
        "run_ids": [row["replay_run_id"] for row in window],
        "budget_status_counts": counts,
        "aggregated_budget_status": aggregate_status,
    }


def _validate_replay_budget_inputs(artifact: Dict[str, Any]) -> None:
    observability = artifact.get("observability_metrics")
    if not isinstance(observability, dict):
        raise ControlLoopError("normalized signal missing required field")
    budget = artifact.get("error_budget_status")
    if not isinstance(budget, dict):
        raise ControlLoopError("normalized signal missing required field")
    budget_schema = load_schema("error_budget_status")
    budget_errors = _validate(budget, budget_schema)
    if budget_errors:
        raise ControlLoopError("error_budget_status failed validation: " + "; ".join(budget_errors))

    metrics = observability.get("metrics")
    if not isinstance(metrics, dict):
        raise ControlLoopError("normalized signal missing required field")
    objectives = budget.get("objectives")
    if not isinstance(objectives, list):
        raise ControlLoopError("normalized signal missing required field")
    objective_by_metric = {
        obj.get("metric_name"): obj for obj in objectives if isinstance(obj, dict) and obj.get("metric_name")
    }
    unmapped_metrics = sorted(
        metric_name
        for metric_name in metrics.keys()
        if metric_name != "total_runs" and metric_name not in objective_by_metric
    )
    if unmapped_metrics:
        raise ControlLoopError(
            "no-dead-metrics violation: observability metrics missing error_budget_status objectives for "
            + ", ".join(unmapped_metrics)
        )
    for metric_name in ("replay_success_rate", "drift_exceed_threshold_rate"):
        metric_value = metrics.get(metric_name)
        objective = objective_by_metric.get(metric_name)
        if isinstance(metric_value, (int, float)) and isinstance(objective, dict):
            observed_value = objective.get("observed_value")
            if not isinstance(observed_value, (int, float)) or abs(float(metric_value) - float(observed_value)) > _OBSERVABILITY_BUDGET_TOLERANCE:
                raise ControlLoopError(
                    "inconsistent replay_result observability_metrics vs error_budget_status for "
                    f"{metric_name}"
                )

    budget_status = budget.get("budget_status")
    highest_severity = budget.get("highest_severity")
    if budget_status not in _ERROR_BUDGET_SEVERITY_ORDER:
        raise ControlLoopError("replay_result.error_budget_status.budget_status must be healthy|warning|exhausted|invalid")
    if highest_severity not in _ERROR_BUDGET_SEVERITY_ORDER:
        raise ControlLoopError("replay_result.error_budget_status.highest_severity must be healthy|warning|exhausted|invalid")
    if _ERROR_BUDGET_SEVERITY_ORDER[highest_severity] > _ERROR_BUDGET_SEVERITY_ORDER[budget_status]:
        raise ControlLoopError("inconsistent replay_result error_budget_status highest_severity exceeds budget_status")
    if _ERROR_BUDGET_SEVERITY_ORDER[budget_status] > _ERROR_BUDGET_SEVERITY_ORDER[highest_severity]:
        raise ControlLoopError("inconsistent replay_result error_budget_status budget_status exceeds highest_severity")
    if budget_status == "healthy" and budget.get("triggered_conditions"):
        raise ControlLoopError("inconsistent replay_result error_budget_status: healthy budget cannot have triggered_conditions")

    replay_timestamp = _parse_rfc3339_utc(artifact.get("timestamp"), field_name="replay_result.timestamp")
    for field_name, source in (
        ("replay_result.observability_metrics.timestamp", observability.get("timestamp")),
        ("replay_result.error_budget_status.timestamp", budget.get("timestamp")),
    ):
        if source is None:
            continue
        nested_timestamp = _parse_rfc3339_utc(source, field_name=field_name)
        if abs((replay_timestamp - nested_timestamp).total_seconds()) > _MAX_EMBEDDED_TIMESTAMP_DELTA_SECONDS:
            raise ControlLoopError(f"stale timestamps detected: {field_name} is too far from replay_result.timestamp")


def _normalize_signal(artifact: Dict[str, Any]) -> Dict[str, Any]:
    artifact_type = artifact.get("artifact_type")
    if artifact_type == "failure_eval_case":
        eval_case_id = str(artifact.get("eval_case_id") or "")
        trace_id = str(artifact.get("trace_id") or "")
        source_artifact_id = str(artifact.get("source_artifact_id") or "")
        run_id = str(artifact.get("source_run_id") or eval_case_id)
        return {
            "signal_type": artifact_type,
            "source_artifact_id": eval_case_id,
            "key_metrics": {
                "failure_class": artifact.get("failure_class"),
                "failure_stage": artifact.get("failure_stage"),
                "source_failure_id": source_artifact_id,
            },
            "trace_id": trace_id,
            "run_id": run_id,
            "artifact_type": artifact_type,
        }
    if artifact_type != "replay_result":
        raise ControlLoopError(f"unsupported artifact_type for control loop: {artifact_type}")
    _validate_replay_budget_inputs(artifact)
    source_artifact_id = str(artifact.get("replay_id") or "")

    return {
        "signal_type": artifact_type,
        "source_artifact_id": source_artifact_id,
        "key_metrics": {
            key: artifact.get(key)
            for key in (
                "pass_rate",
                "failure_rate",
                "drift_rate",
                "reproducibility_score",
                "indeterminate_failure_count",
            )
            if key in artifact
        },
        "trace_id": str(artifact.get("trace_id") or ""),
        "run_id": str(artifact.get("replay_run_id") or source_artifact_id or ""),
        "artifact_type": artifact_type,
    }


def _validate_normalized_signal(signal: Dict[str, Any]) -> None:
    required = ("signal_type", "source_artifact_id", "trace_id", "run_id")
    for key in required:
        value = signal.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ControlLoopError(f"normalized signal missing required field: {key}")


def _validate_trace_context_binding(
    trace_context: Dict[str, Any],
    artifact: Dict[str, Any],
) -> None:
    if artifact.get("artifact_type") == "failure_eval_case":
        required_linkage = ("trace_id",)
        for key in required_linkage:
            trace_value = trace_context.get(key)
            if not isinstance(trace_value, str) or not trace_value.strip():
                raise ControlLoopError(f"trace_context missing required linkage field: {key}")
            artifact_value = artifact.get(key)
            if not isinstance(artifact_value, str) or not artifact_value.strip():
                raise ControlLoopError(f"artifact missing required trace linkage field: {key}")
            if trace_value != artifact_value:
                raise ControlLoopError(
                    f"trace_context linkage mismatch for {key}: expected artifact identity binding"
                )
        return
    required_linkage = ("trace_id", "replay_id", "replay_run_id")
    for key in required_linkage:
        trace_value = trace_context.get(key)
        if not isinstance(trace_value, str) or not trace_value.strip():
            raise ControlLoopError(f"trace_context missing required linkage field: {key}")

        artifact_value = artifact.get(key)
        if not isinstance(artifact_value, str) or not artifact_value.strip():
            raise ControlLoopError(f"artifact missing required trace linkage field: {key}")

        if trace_value != artifact_value:
            raise ControlLoopError(
                f"trace_context linkage mismatch for {key}: expected artifact identity binding"
            )


def build_trace_context_from_replay_artifact(
    artifact: Dict[str, Any],
    *,
    base_context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    if not isinstance(artifact, dict):
        raise ControlLoopError("artifact must be a dict")

    trace_context = dict(base_context or {})
    for key in ("trace_id", "replay_id", "replay_run_id"):
        value = artifact.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ControlLoopError(f"artifact missing required trace linkage field: {key}")
        trace_context[key] = value
    return trace_context


def _evaluate_signal(
    signal: Dict[str, Any],
    artifact: Dict[str, Any],
    trace_context: Dict[str, Any],
) -> Dict[str, Any]:
    signal_type = signal["signal_type"]

    if signal_type == "replay_result":
        try:
            return build_evaluation_control_decision(artifact)
        except EvaluationControlError as exc:
            raise ControlLoopError(str(exc)) from exc
    if signal_type == "failure_eval_case":
        registry = trace_context.get("failure_eval_registry")
        if not isinstance(registry, dict):
            raise ControlLoopError("failure_eval_case requires failure_eval_registry in trace_context")
        eval_case_id = str(artifact.get("eval_case_id") or "")
        binding = registry.get(eval_case_id)
        if not isinstance(binding, dict):
            raise ControlLoopError("failure_eval_case is not registered in failure_eval_registry")
        try:
            return build_evaluation_control_decision(
                artifact,
                failure_policy_binding=binding,
            )
        except EvaluationControlError as exc:
            raise ControlLoopError(str(exc)) from exc

    raise ControlLoopError(f"unsupported signal_type for evaluation stage: {signal_type}")


def _validate_control_trace(control_trace: Dict[str, Any]) -> None:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "trace_id",
            "run_id",
            "input_artifact_id",
            "signal_type",
            "evaluation_path",
            "decision",
            "timestamp",
        ],
        "properties": {
            "trace_id": {"type": "string", "minLength": 1},
            "run_id": {"type": "string", "minLength": 1},
            "input_artifact_id": {"type": "string", "minLength": 1},
            "signal_type": {"type": "string", "enum": ["replay_result", "failure_eval_case"]},
            "evaluation_path": {
                "type": "string",
                "enum": ["evaluation_control_from_replay_result", "evaluation_control_from_failure_eval_case"],
            },
            "decision": {"type": "string", "enum": ["allow", "deny", "require_review"]},
            "timestamp": {"type": "string", "format": "date-time"},
        },
    }
    errors = _validate(control_trace, schema)
    if errors:
        raise ControlLoopError("control_trace failed validation: " + "; ".join(errors))


def run_control_loop(
    artifact: Dict[str, Any],
    trace_context: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """Run deterministic control loop and return decision + structured control trace."""
    if not isinstance(artifact, dict):
        raise ControlLoopError("artifact must be a dict")
    if not isinstance(trace_context, dict):
        raise ControlLoopError("trace_context must be a dict")

    signal = _normalize_signal(artifact)
    _validate_normalized_signal(signal)
    _validate_trace_context_binding(trace_context, artifact)

    decision = _evaluate_signal(signal, artifact, trace_context)
    decision_schema = load_schema("evaluation_control_decision")
    decision_errors = _validate(decision, decision_schema)
    if decision_errors:
        raise ControlLoopError(
            "evaluation_control_decision failed schema validation: " + "; ".join(decision_errors)
        )
    if signal["signal_type"] == "replay_result":
        budget_status = str((artifact.get("error_budget_status") or {}).get("budget_status") or "invalid")
        if budget_status == "exhausted" and decision.get("system_response") not in {"freeze", "block"}:
            raise ControlLoopError("budget exceeded without deterministic enforcement action")
    if signal["signal_type"] == "failure_eval_case":
        binding = (trace_context.get("failure_eval_registry") or {}).get(str(artifact.get("eval_case_id") or ""))
        if isinstance(binding, dict) and binding.get("recurrence_prevention_artifact"):
            if decision.get("decision") == "allow":
                raise ControlLoopError("recurrence prevention authority not consumed by control decision")
        else:
            raise ControlLoopError("failure_eval_case recurrence prevention artifact missing from registry binding")

    control_trace = {
        "trace_id": decision["trace_id"],
        "run_id": decision["run_id"],
        "input_artifact_id": signal["source_artifact_id"],
        "signal_type": signal["signal_type"],
        "evaluation_path": (
            "evaluation_control_from_failure_eval_case"
            if signal["signal_type"] == "failure_eval_case"
            else "evaluation_control_from_replay_result"
        ),
        "decision": decision["decision"],
        "timestamp": decision["created_at"],
    }
    _validate_control_trace(control_trace)

    return {
        "evaluation_control_decision": decision,
        "control_trace": control_trace,
    }


def run_judgment_learning_control_loop(
    *,
    judgment_eval_result: Dict[str, Any] | None,
    judgment_calibration_result: Dict[str, Any] | None,
    judgment_drift_signal: Dict[str, Any] | None,
    judgment_error_budget_status: Dict[str, Any] | None,
    judgment_policy: Dict[str, Any] | None,
    trace_context: Dict[str, Any],
    created_at: str,
) -> Dict[str, Any]:
    """Deterministic learning-signal control decision with governed escalation record output."""
    required = {
        "judgment_eval_result": (judgment_eval_result, "judgment_eval_result"),
        "judgment_calibration_result": (judgment_calibration_result, "judgment_calibration_result"),
        "judgment_drift_signal": (judgment_drift_signal, "judgment_drift_signal"),
        "judgment_error_budget_status": (judgment_error_budget_status, "judgment_error_budget_status"),
        "judgment_policy": (judgment_policy, "judgment_policy"),
    }
    fail_closed_reasons: list[str] = []
    for name, (payload, schema_name) in required.items():
        if not isinstance(payload, dict):
            fail_closed_reasons.append(f"missing required artifact: {name}")
            continue
        errors = _validate(payload, load_schema(schema_name))
        if errors:
            fail_closed_reasons.append(f"invalid {name}: {'; '.join(errors)}")

    run_id = str(trace_context.get("replay_run_id") or trace_context.get("run_id") or "")
    trace_id = str(trace_context.get("trace_id") or "")
    if not run_id or not trace_id:
        fail_closed_reasons.append("missing required trace linkage")

    drift_eval = {
        "status": "critical_drift",
        "group_results": [],
        "thresholds": {},
    }
    if not fail_closed_reasons:
        drift_eval = evaluate_judgment_drift_threshold_policy(
            artifact_id=f"{judgment_drift_signal['artifact_id']}-threshold-eval",
            drift_signal=judgment_drift_signal,
            policy=judgment_policy,
            created_at=created_at,
        )

    decision = "allow"
    rationale: list[str] = []
    triggering_signals: dict[str, Any] = {
        "drift": drift_eval["status"],
        "calibration": "healthy",
        "error_budget": str((judgment_error_budget_status or {}).get("status") or "invalid"),
    }
    thresholds_used = {
        "drift": drift_eval.get("thresholds", {}),
        "calibration": (((judgment_policy or {}).get("learning_control_policy") or {}).get("calibration") or {}),
        "error_budget": (((judgment_policy or {}).get("learning_control_policy") or {}).get("error_budget_limits") or {}),
    }

    if fail_closed_reasons:
        decision = "block"
        rationale.extend(fail_closed_reasons)
    else:
        eval_failures = [
            item.get("eval_type")
            for item in judgment_eval_result.get("eval_results", [])
            if isinstance(item, dict) and item.get("passed") is not True
        ]
        if eval_failures:
            decision = "block"
            rationale.append(f"required eval failures: {', '.join(sorted(str(item) for item in eval_failures))}")

        budget_status = str(judgment_error_budget_status.get("status") or "invalid")
        if budget_status == "exhausted":
            decision = "block"
            rationale.append("judgment error budget exhausted")
        elif budget_status == "warning" and decision == "allow":
            decision = "warn"
            rationale.append("judgment error budget warning")
        elif budget_status not in {"healthy", "warning", "exhausted"}:
            decision = "block"
            rationale.append("invalid judgment error budget status")

        if drift_eval["status"] == "critical_drift":
            decision = "block"
            rationale.append("critical drift detected")
        elif drift_eval["status"] == "warning_drift" and decision in {"allow", "warn"}:
            decision = "freeze"
            rationale.append("warning drift threshold exceeded")

        calibration_policy = ((judgment_policy.get("learning_control_policy") or {}).get("calibration")) or {}
        warn_ece = float(calibration_policy.get("warn_if_expected_calibration_error_greater_than", 0.05))
        freeze_ece = float(calibration_policy.get("freeze_if_expected_calibration_error_greater_than", 0.1))
        max_ece = 0.0
        for row in judgment_calibration_result.get("group_metrics", []):
            if isinstance(row, dict):
                max_ece = max(max_ece, float(row.get("expected_calibration_error", 0.0)))
        if max_ece >= freeze_ece and decision != "block":
            decision = "freeze"
            triggering_signals["calibration"] = "degraded_freeze_band"
            rationale.append("calibration degradation exceeded freeze band")
        elif max_ece >= warn_ece and decision == "allow":
            decision = "warn"
            triggering_signals["calibration"] = "degraded_warn_band"
            rationale.append("calibration degradation within warning tolerance")

        override_warn = float((judgment_policy.get("learning_control_policy") or {}).get("override_rate_warn_if_greater_than", 0.15))
        has_rising_override = any(
            float(((row.get("rates") or {}).get("override_rate") or 0.0)) >= override_warn
            for row in judgment_error_budget_status.get("group_statuses", [])
            if isinstance(row, dict)
        )
        if has_rising_override and decision == "allow":
            decision = "warn"
            rationale.append("override rate rising")

    escalation = {
        "artifact_type": "judgment_control_escalation_record",
        "artifact_id": f"judgment-control-escalation-{run_id}",
        "artifact_version": "1.1.0",
        "schema_version": "1.1.0",
        "standards_version": "1.0.95",
        "decision": decision,
        "triggering_signals": triggering_signals,
        "thresholds_used": thresholds_used,
        "rationale": sorted(set(rationale)) or ["all checks passed"],
        "trace": {
            "trace_id": trace_id,
            "run_id": run_id,
            "judgment_eval_result_id": str((judgment_eval_result or {}).get("artifact_id") or "missing"),
            "judgment_calibration_result_id": str((judgment_calibration_result or {}).get("artifact_id") or "missing"),
            "judgment_drift_signal_id": str((judgment_drift_signal or {}).get("artifact_id") or "missing"),
            "judgment_error_budget_status_id": str((judgment_error_budget_status or {}).get("artifact_id") or "missing"),
            "judgment_policy_id": str((judgment_policy or {}).get("artifact_id") or "missing"),
            "judgment_policy_version": str((judgment_policy or {}).get("artifact_version") or "missing"),
            "policy_lifecycle_status": str((judgment_policy or {}).get("status") or "unknown"),
            "policy_rollout_id": str(((judgment_policy or {}).get("_selected_rollout_id")) or "none"),
        },
        "created_at": created_at,
    }
    escalation_errors = _validate(escalation, load_schema("judgment_control_escalation_record"))
    if escalation_errors:
        raise ControlLoopError(
            "judgment_control_escalation_record failed validation: " + "; ".join(escalation_errors)
        )

    enforcement = build_judgment_enforcement_artifacts(
        escalation,
        created_at=created_at,
    )

    return {
        "decision": decision,
        "judgment_control_escalation_record": escalation,
        "judgment_enforcement_action_record": enforcement["judgment_enforcement_action_record"],
        "judgment_enforcement_outcome_record": enforcement["judgment_enforcement_outcome_record"],
        "judgment_operator_remediation_record": enforcement["judgment_operator_remediation_record"],
        "progression_allowed": enforcement["progression_allowed"],
        "enforcement_blocking_reasons": enforcement["blocking_reasons"],
        "drift_threshold_evaluation": drift_eval,
    }
