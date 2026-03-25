"""Deterministic alert trigger decisioning from replay-authoritative governed artifacts."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema

SCHEMA_VERSION = "1.0.0"
_GENERATED_BY_VERSION = "alert_triggers.py@1.0.0"


class AlertTriggerError(ValueError):
    """Raised when alert trigger evaluation fails closed."""


def _validate_or_raise(instance: Dict[str, Any], schema_name: str, *, context: str) -> None:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise AlertTriggerError(f"{context} failed validation: {details}")


def _stable_id(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _require_non_empty_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AlertTriggerError(f"{field_name} must be a non-empty string")
    return value


def _default_policy() -> Dict[str, Any]:
    return {
        "artifact_type": "alert_trigger_policy",
        "schema_version": "1.0.0",
        "policy_id": "sre-alert-trigger-policy-v1",
        "supported_signal_types": [
            "error_budget_status",
            "observability_metrics",
            "baseline_gate_decision",
            "drift_detection_result",
            "grounding_control_decision",
        ],
        "required_source_artifacts": [
            "replay_result",
            "observability_metrics",
            "error_budget_status",
        ],
        "budget_status_to_alert": {
            "healthy": {"alert_status": "no_alert", "severity": "none", "condition": "budget_healthy"},
            "warning": {"alert_status": "warning", "severity": "medium", "condition": "budget_warning"},
            "exhausted": {"alert_status": "critical", "severity": "critical", "condition": "budget_exhausted"},
            "invalid": {"alert_status": "invalid", "severity": "high", "condition": "budget_invalid"},
        },
        "breach_severity_to_alert": {
            "none": {"alert_status": "no_alert", "severity": "none", "condition": "no_breach"},
            "warn": {"alert_status": "warning", "severity": "medium", "condition": "slo_warn_breach"},
            "block": {"alert_status": "critical", "severity": "high", "condition": "slo_block_breach"},
        },
        "baseline_gate_status_to_alert": {
            "pass": {"alert_status": "no_alert", "severity": "none", "condition": "baseline_pass"},
            "warn": {"alert_status": "warning", "severity": "low", "condition": "baseline_warn"},
            "block": {"alert_status": "critical", "severity": "high", "condition": "baseline_block"},
        },
        "drift_status_to_alert": {
            "no_drift": {"alert_status": "no_alert", "severity": "none", "condition": "drift_none"},
            "within_threshold": {"alert_status": "warning", "severity": "low", "condition": "drift_within_threshold"},
            "exceeds_threshold": {"alert_status": "critical", "severity": "high", "condition": "drift_exceeds_threshold"},
            "invalid_comparison": {"alert_status": "invalid", "severity": "high", "condition": "drift_invalid_comparison"},
        },
        "grounding_status_to_alert": {
            "pass": {"alert_status": "no_alert", "severity": "none", "condition": "grounding_pass"},
            "warn": {"alert_status": "warning", "severity": "low", "condition": "grounding_warn"},
            "block": {"alert_status": "critical", "severity": "high", "condition": "grounding_block"},
        },
        "invalid_input_behavior": "emit_invalid_alert",
        "recommended_actions": {
            "no_alert": "none",
            "warning": "observe",
            "critical": "open_investigation",
            "invalid": "fix_input_contracts",
        },
        "generated_by_version": "sre-11@1.0.0",
    }


def load_alert_trigger_policy(policy: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Load and validate governed alert policy, falling back to canonical default."""
    resolved = deepcopy(policy) if policy is not None else _default_policy()
    _validate_or_raise(resolved, "alert_trigger_policy", context="alert_trigger_policy")
    return resolved


def _source_schema_for_artifact_type(artifact_type: str) -> Optional[str]:
    return {
        "observability_metrics": "observability_metrics",
        "error_budget_status": "error_budget_status",
        "baseline_gate_decision": "baseline_gate_decision",
        "drift_detection_result": "drift_detection_result",
        "grounding_control_decision": "grounding_control_decision",
    }.get(artifact_type)


def _mapping_for_signal(policy: Dict[str, Any], signal_type: str) -> Dict[str, Dict[str, str]]:
    return {
        "error_budget_status": policy["budget_status_to_alert"],
        "observability_metrics": policy["breach_severity_to_alert"],
        "baseline_gate_decision": policy["baseline_gate_status_to_alert"],
        "drift_detection_result": policy["drift_status_to_alert"],
        "grounding_control_decision": policy["grounding_status_to_alert"],
    }[signal_type]


def _signal_value(source: Dict[str, Any], signal_type: str) -> str:
    if signal_type == "error_budget_status":
        return _require_non_empty_str(source.get("budget_status"), "error_budget_status.budget_status")
    if signal_type == "observability_metrics":
        breach_summary = source.get("breach_summary")
        if not isinstance(breach_summary, dict):
            raise AlertTriggerError("observability_metrics.breach_summary must be an object")
        return _require_non_empty_str(breach_summary.get("highest_severity"), "observability_metrics.breach_summary.highest_severity")
    if signal_type == "baseline_gate_decision":
        return _require_non_empty_str(source.get("status"), "baseline_gate_decision.status")
    if signal_type == "drift_detection_result":
        return _require_non_empty_str(source.get("drift_status"), "drift_detection_result.drift_status")
    if signal_type == "grounding_control_decision":
        return _require_non_empty_str(source.get("status"), "grounding_control_decision.status")
    raise AlertTriggerError(f"unsupported signal_type: {signal_type!r}")


def _artifact_identifier(artifact: Dict[str, Any]) -> str:
    for field in ("artifact_id", "replay_id", "decision_id"):
        value = artifact.get(field)
        if isinstance(value, str) and value.strip():
            return value
    raise AlertTriggerError("source artifact is missing deterministic identity field")


def _extract_sources(replay_result: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    sources: Dict[str, Dict[str, Any]] = {"replay_result": replay_result}
    for key in (
        "observability_metrics",
        "error_budget_status",
        "baseline_gate_decision",
        "drift_detection_result",
        "grounding_control_decision",
    ):
        value = replay_result.get(key)
        if isinstance(value, dict):
            sources[key] = deepcopy(value)
    return sources


def _severity_rank(severity: str) -> int:
    return {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}[severity]


def _status_rank(status: str) -> int:
    return {"no_alert": 0, "warning": 1, "critical": 2, "invalid": 3}[status]


def _merge_decision(
    current_status: str,
    current_severity: str,
    candidate_status: str,
    candidate_severity: str,
) -> Tuple[str, str]:
    if _status_rank(candidate_status) > _status_rank(current_status):
        return candidate_status, candidate_severity
    if _status_rank(candidate_status) == _status_rank(current_status) and _severity_rank(candidate_severity) > _severity_rank(current_severity):
        return candidate_status, candidate_severity
    return current_status, current_severity


def build_alert_trigger(
    replay_result: Dict[str, Any],
    policy: Optional[Dict[str, Any]] = None,
    *,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build deterministic governed alert trigger from replay-authoritative artifacts."""
    if not isinstance(replay_result, dict):
        raise AlertTriggerError("replay_result must be an object")

    replay_input = deepcopy(replay_result)
    _validate_or_raise(replay_input, "replay_result", context="replay_result")
    resolved_policy = load_alert_trigger_policy(policy)

    sources = _extract_sources(replay_input)
    missing = [artifact_type for artifact_type in resolved_policy["required_source_artifacts"] if artifact_type not in sources]

    replay_id = _require_non_empty_str(replay_input.get("replay_id"), "replay_result.replay_id")
    resolved_trace_id = _require_non_empty_str(
        trace_id or replay_input.get("trace_id"),
        "trace_id",
    )
    timestamp = _require_non_empty_str(replay_input.get("timestamp"), "replay_result.timestamp")

    source_artifact_ids = sorted({_artifact_identifier(value) for value in sources.values()})

    alert_status = "no_alert"
    severity = "none"
    triggered_conditions: List[str] = []
    reasons: List[str] = []

    if missing:
        if resolved_policy["invalid_input_behavior"] != "emit_invalid_alert":
            raise AlertTriggerError("alert_trigger_policy.invalid_input_behavior is unsupported")
        alert_status = "invalid"
        severity = "high"
        triggered_conditions = ["missing_required_source_artifacts"]
        reasons = ["missing_required_source_artifacts"]
    else:
        for signal_type in resolved_policy["supported_signal_types"]:
            if signal_type not in sources:
                continue
            source = sources[signal_type]
            source_schema = _source_schema_for_artifact_type(signal_type)
            if source_schema is None:
                raise AlertTriggerError(f"unsupported signal_type in policy: {signal_type!r}")
            _validate_or_raise(source, source_schema, context=f"{signal_type} source artifact")
            value = _signal_value(source, signal_type)
            mapping = _mapping_for_signal(resolved_policy, signal_type)
            if value not in mapping:
                raise AlertTriggerError(f"unknown {signal_type} vocabulary value: {value!r}")
            mapped = mapping[value]
            candidate_status = mapped["alert_status"]
            candidate_severity = mapped["severity"]
            alert_status, severity = _merge_decision(
                alert_status,
                severity,
                candidate_status,
                candidate_severity,
            )
            if candidate_status != "no_alert":
                triggered_conditions.append(mapped["condition"])
                reasons.append(mapped["condition"])

    if not reasons and alert_status == "no_alert":
        reasons = ["no_alert_conditions_detected"]

    recommended_action = resolved_policy["recommended_actions"][alert_status]

    preimage = {
        "timestamp": timestamp,
        "trace_id": resolved_trace_id,
        "replay_result_id": replay_id,
        "policy_id": resolved_policy["policy_id"],
        "source_artifact_ids": source_artifact_ids,
        "alert_status": alert_status,
        "severity": severity,
        "triggered_conditions": sorted(set(triggered_conditions)),
        "reasons": sorted(set(reasons)),
        "recommended_action": recommended_action,
    }

    result = {
        "artifact_id": _stable_id(preimage),
        "artifact_type": "alert_trigger",
        "schema_version": SCHEMA_VERSION,
        "timestamp": timestamp,
        "trace_refs": {"trace_id": resolved_trace_id},
        "replay_result_id": replay_id,
        "source_artifact_ids": source_artifact_ids,
        "policy_id": _require_non_empty_str(resolved_policy.get("policy_id"), "alert_trigger_policy.policy_id"),
        "alert_status": alert_status,
        "severity": severity,
        "triggered_conditions": sorted(set(triggered_conditions)),
        "reasons": sorted(set(reasons)),
        "recommended_action": recommended_action,
        "generated_by_version": _GENERATED_BY_VERSION,
    }
    _validate_or_raise(result, "alert_trigger", context="alert_trigger")
    return result
