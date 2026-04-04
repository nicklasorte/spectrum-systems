"""Deterministic governed exception classification and resolution routing."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class ExceptionRouterError(ValueError):
    """Raised when exception classification/routing cannot be computed safely."""


_EXCEPTION_CLASSES = {
    "missing_eval_coverage",
    "missing_required_eval_result",
    "indeterminate_required_eval",
    "replay_mismatch",
    "review_required",
    "autonomy_blocked",
    "program_misalignment",
    "drift_detected",
    "unresolved_critical_risk",
    "policy_violation",
    "execution_failure",
    "unknown_blocker",
}


def _canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _validate_schema(instance: dict[str, Any], schema_name: str) -> None:
    validator = Draft202012Validator(load_schema(schema_name), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise ExceptionRouterError(f"{schema_name} validation failed: {details}")


def _sorted_unique_strings(values: list[Any]) -> list[str]:
    return sorted({str(item).strip() for item in values if str(item).strip()})


def _failure_key_signals(failure_keys: list[str], token: str) -> bool:
    return any(token in key.lower() for key in failure_keys)


def _normalize_replay_status(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"match", "passed", "pass", "ready"}:
        return "match"
    if normalized in {"mismatch", "failed", "fail", "not_ready"}:
        return "mismatch"
    return "unknown"


def classify_exception_state(
    *,
    source_artifact_ref: str,
    source_batch_id: str,
    source_cycle_id: str,
    control_decision: str,
    autonomy_decision: str,
    stop_reason: str,
    blocking_conditions: list[str] | None,
    drift_signals: dict[str, Any] | None,
    replay_status: str,
    review_gate_status: str,
    missing_eval_enforcement_artifacts: list[str] | None,
    unresolved_critical_risks: list[str] | None,
    failure_keys: list[str] | None,
    created_at: str,
    trace_id: str,
) -> dict[str, Any]:
    """Classify a governed exception state from normalized deterministic signals."""

    required_text = {
        "source_artifact_ref": source_artifact_ref,
        "source_batch_id": source_batch_id,
        "source_cycle_id": source_cycle_id,
        "control_decision": control_decision,
        "autonomy_decision": autonomy_decision,
        "stop_reason": stop_reason,
        "created_at": created_at,
        "trace_id": trace_id,
    }
    for field, value in required_text.items():
        if not isinstance(value, str) or not value.strip():
            raise ExceptionRouterError(f"{field} is required for deterministic exception classification")

    if not isinstance(drift_signals, dict):
        raise ExceptionRouterError("drift_signals is required and must be an object")

    blocking = _sorted_unique_strings(list(blocking_conditions or []))
    missing_eval = _sorted_unique_strings(list(missing_eval_enforcement_artifacts or []))
    unresolved_critical = _sorted_unique_strings(list(unresolved_critical_risks or []))
    failure = _sorted_unique_strings(
        [item for item in list(failure_keys or []) if str(item).strip().lower() not in {"max_batches_reached", "healthy_aligned_progress"}]
    )

    replay = _normalize_replay_status(replay_status)
    review_gate = str(review_gate_status).strip().lower() or "unknown"
    drift_level = str(drift_signals.get("drift_level") or "unknown").strip().lower()
    normalized_failure_keys = _sorted_unique_strings(failure + missing_eval + blocking)

    stop_reason_norm = stop_reason.strip().lower()
    control_norm = control_decision.strip().lower()
    autonomy_norm = autonomy_decision.strip().lower()

    if _failure_key_signals(normalized_failure_keys, "policy") or stop_reason_norm == "contract_precondition_failed":
        exception_class = "policy_violation"
        severity = "critical"
    elif _failure_key_signals(normalized_failure_keys, "missing_eval_coverage"):
        exception_class = "missing_eval_coverage"
        severity = "high"
    elif _failure_key_signals(normalized_failure_keys, "missing_required_eval_result"):
        exception_class = "missing_required_eval_result"
        severity = "high"
    elif _failure_key_signals(normalized_failure_keys, "indeterminate_required_eval"):
        exception_class = "indeterminate_required_eval"
        severity = "critical"
    elif replay == "mismatch" or stop_reason_norm == "replay_not_ready" or _failure_key_signals(normalized_failure_keys, "replay_mismatch"):
        exception_class = "replay_mismatch"
        severity = "critical"
    elif review_gate in {"required", "pending"} or stop_reason_norm == "manual_review_required":
        exception_class = "review_required"
        severity = "high"
    elif autonomy_norm in {"require_human_review", "stop", "escalate"}:
        exception_class = "autonomy_blocked"
        severity = "high"
    elif stop_reason_norm in {"program_alignment_invalid", "program_priority_violation", "program_blocking_condition"}:
        exception_class = "program_misalignment"
        severity = "high"
    elif drift_level == "high" or stop_reason_norm == "program_drift_detected":
        exception_class = "drift_detected"
        severity = "high"
    elif unresolved_critical:
        exception_class = "unresolved_critical_risk"
        severity = "critical"
    elif stop_reason_norm == "max_batches_reached" and not normalized_failure_keys:
        exception_class = "execution_failure"
        severity = "low"
    elif stop_reason_norm in {"execution_failed", "execution_blocked", "loop_validation_failed"} or control_norm in {"block", "freeze"}:
        exception_class = "execution_failure"
        severity = "high"
    elif normalized_failure_keys:
        exception_class = "unknown_blocker"
        severity = "high"
    else:
        raise ExceptionRouterError("unable to classify exception state; no governed blocker signals present")

    if exception_class not in _EXCEPTION_CLASSES:
        raise ExceptionRouterError(f"unsupported exception_class computed: {exception_class}")

    seed = {
        "source_artifact_ref": source_artifact_ref,
        "source_batch_id": source_batch_id,
        "source_cycle_id": source_cycle_id,
        "control_decision": control_norm,
        "autonomy_decision": autonomy_norm,
        "stop_reason": stop_reason_norm,
        "exception_class": exception_class,
        "severity": severity,
        "normalized_failure_keys": normalized_failure_keys,
        "trace_id": trace_id,
    }
    record = {
        "exception_classification_id": f"ECR-{_canonical_hash(seed)[:12].upper()}",
        "source_artifact_ref": source_artifact_ref,
        "source_batch_id": source_batch_id,
        "source_cycle_id": source_cycle_id,
        "control_decision": control_norm,
        "autonomy_decision": autonomy_norm,
        "stop_reason": stop_reason_norm,
        "exception_class": exception_class,
        "severity": severity,
        "normalized_failure_keys": normalized_failure_keys,
        "created_at": created_at,
        "trace_id": trace_id,
    }
    _validate_schema(record, "exception_classification_record")
    return record


def route_exception_resolution(
    *,
    exception_classification_record: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    """Route a classified governed exception state to deterministic next action."""
    _validate_schema(exception_classification_record, "exception_classification_record")
    if not isinstance(created_at, str) or not created_at.strip():
        raise ExceptionRouterError("created_at is required for deterministic exception resolution routing")

    exception_class = str(exception_classification_record["exception_class"])
    blocking_conditions = [
        key for key in exception_classification_record.get("normalized_failure_keys", []) if key.startswith("AUTH_") or key.startswith("PROP_")
    ]

    route_map: dict[str, dict[str, Any]] = {
        "missing_eval_coverage": {
            "recommended_action": "create_eval_coverage_work",
            "action_type": "create_eval_batch",
            "route_target": "eval_pipeline",
            "requires_human_review": False,
            "requires_roadmap_adjustment": False,
            "requires_freeze": False,
            "required_followup_artifacts": ["required_eval_registry", "eval_coverage_summary"],
        },
        "missing_required_eval_result": {
            "recommended_action": "re_run_or_remediate_eval_path",
            "action_type": "create_eval_batch",
            "route_target": "eval_pipeline",
            "requires_human_review": False,
            "requires_roadmap_adjustment": False,
            "requires_freeze": False,
            "required_followup_artifacts": ["evaluation_control_decision", "evaluation_enforcement_action"],
        },
        "indeterminate_required_eval": {
            "recommended_action": "freeze_and_investigate",
            "action_type": "freeze_and_investigate",
            "route_target": "investigation_queue",
            "requires_human_review": True,
            "requires_roadmap_adjustment": False,
            "requires_freeze": True,
            "required_followup_artifacts": ["evaluation_control_decision", "review_request"],
        },
        "replay_mismatch": {
            "recommended_action": "freeze_and_replay_investigation",
            "action_type": "freeze_and_investigate",
            "route_target": "replay_governance",
            "requires_human_review": True,
            "requires_roadmap_adjustment": False,
            "requires_freeze": True,
            "required_followup_artifacts": ["replay_result", "review_request"],
        },
        "review_required": {
            "recommended_action": "queue_review",
            "action_type": "queue_review",
            "route_target": "review_queue",
            "requires_human_review": True,
            "requires_roadmap_adjustment": False,
            "requires_freeze": False,
            "required_followup_artifacts": ["review_request", "review_artifact"],
        },
        "autonomy_blocked": {
            "recommended_action": "require_human_review",
            "action_type": "stop_without_auto_action",
            "route_target": "operator_review",
            "requires_human_review": True,
            "requires_roadmap_adjustment": False,
            "requires_freeze": False,
            "required_followup_artifacts": ["autonomy_decision_record", "review_request"],
        },
        "program_misalignment": {
            "recommended_action": "roadmap_adjustment",
            "action_type": "adjust_roadmap",
            "route_target": "roadmap_governance",
            "requires_human_review": True,
            "requires_roadmap_adjustment": True,
            "requires_freeze": False,
            "required_followup_artifacts": ["program_roadmap_alignment_result", "roadmap_artifact"],
        },
        "drift_detected": {
            "recommended_action": "freeze_and_investigate",
            "action_type": "freeze_and_investigate",
            "route_target": "drift_response",
            "requires_human_review": True,
            "requires_roadmap_adjustment": False,
            "requires_freeze": True,
            "required_followup_artifacts": ["drift_detection_result", "drift_remediation_artifact"],
        },
        "unresolved_critical_risk": {
            "recommended_action": "remediation_batch",
            "action_type": "create_remediation_batch",
            "route_target": "remediation_queue",
            "requires_human_review": True,
            "requires_roadmap_adjustment": False,
            "requires_freeze": False,
            "required_followup_artifacts": ["risk_register", "remediation_plan"],
        },
        "policy_violation": {
            "recommended_action": "escalate",
            "action_type": "escalate",
            "route_target": "policy_authority",
            "requires_human_review": True,
            "requires_roadmap_adjustment": False,
            "requires_freeze": True,
            "required_followup_artifacts": ["control_execution_result", "review_request"],
        },
        "execution_failure": {
            "recommended_action": "remediation_batch",
            "action_type": "create_remediation_batch",
            "route_target": "remediation_queue",
            "requires_human_review": False,
            "requires_roadmap_adjustment": False,
            "requires_freeze": False,
            "required_followup_artifacts": ["next_step_recommendation", "remediation_plan"],
        },
        "unknown_blocker": {
            "recommended_action": "require_human_review",
            "action_type": "stop_without_auto_action",
            "route_target": "operator_review",
            "requires_human_review": True,
            "requires_roadmap_adjustment": False,
            "requires_freeze": True,
            "required_followup_artifacts": ["review_request"],
        },
    }
    if exception_class not in route_map:
        raise ExceptionRouterError(f"unsupported exception class for routing: {exception_class}")

    route = route_map[exception_class]
    seed = {
        "exception_classification_ref": f"exception_classification_record:{exception_classification_record['exception_classification_id']}",
        "recommended_action": route["recommended_action"],
        "action_type": route["action_type"],
        "route_target": route["route_target"],
        "blocking_conditions": sorted(set(blocking_conditions)),
        "trace_id": exception_classification_record["trace_id"],
    }

    record = {
        "exception_resolution_id": f"ERR-{_canonical_hash(seed)[:12].upper()}",
        "exception_classification_ref": seed["exception_classification_ref"],
        "recommended_action": route["recommended_action"],
        "action_type": route["action_type"],
        "route_target": route["route_target"],
        "requires_human_review": route["requires_human_review"],
        "requires_roadmap_adjustment": route["requires_roadmap_adjustment"],
        "requires_freeze": route["requires_freeze"],
        "required_followup_artifacts": sorted(set(route["required_followup_artifacts"])),
        "blocking_conditions": sorted(set(blocking_conditions)),
        "created_at": created_at,
        "trace_id": str(exception_classification_record["trace_id"]),
    }
    _validate_schema(record, "exception_resolution_record")
    return record


__all__ = [
    "ExceptionRouterError",
    "classify_exception_state",
    "route_exception_resolution",
]
