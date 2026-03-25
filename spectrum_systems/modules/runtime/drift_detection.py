"""Deterministic baseline drift detection for governed replay artifacts."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Dict, List

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema

_GENERATED_BY_VERSION = "drift_detection.py@1.0.0"
_ALLOWED_DIMENSIONS = (
    "final_status_delta",
    "enforcement_action_delta",
    "consistency_mismatch_delta",
    "drift_detected_delta",
    "failure_reason_present_delta",
)


class DriftDetectionError(Exception):
    """Raised when baseline drift detection fails-closed."""


def _validate_or_raise(instance: Dict[str, Any], schema_name: str, *, context: str) -> None:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise DriftDetectionError(f"{context} failed validation: {details}")


def _policy_dimension_thresholds(policy: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    if not isinstance(policy, dict):
        raise DriftDetectionError("baseline_gate_policy must be an object")
    _validate_or_raise(policy, "baseline_gate_policy", context="baseline_gate_policy")

    supported_dimensions = list(policy.get("supported_dimensions") or [])
    if supported_dimensions != list(_ALLOWED_DIMENSIONS):
        raise DriftDetectionError(
            "baseline_gate_policy supported_dimensions must exactly match canonical drift dimensions"
        )

    thresholds = policy.get("thresholds")
    if not isinstance(thresholds, dict):
        raise DriftDetectionError("baseline_gate_policy.thresholds must be an object")

    normalized: Dict[str, Dict[str, float]] = {}
    for dim in _ALLOWED_DIMENSIONS:
        entry = thresholds.get(dim)
        if not isinstance(entry, dict):
            raise DriftDetectionError(f"baseline_gate_policy.thresholds[{dim}] must be an object")
        warn = float(entry.get("warn_if_greater_than"))
        block = float(entry.get("block_if_greater_than"))
        if warn > block:
            raise DriftDetectionError(
                f"baseline_gate_policy.thresholds[{dim}] warn_if_greater_than must be <= block_if_greater_than"
            )
        normalized[dim] = {"warn": warn, "block": block}
    return normalized


def _stable_artifact_id(payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _require_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DriftDetectionError(f"{field_name} must be a non-empty string")
    return value


def _extract_metrics(current_artifact: Dict[str, Any], baseline_artifact: Dict[str, Any]) -> Dict[str, float]:
    current_status = _require_non_empty_string(current_artifact.get("replay_final_status"), "current replay_final_status")
    baseline_status = _require_non_empty_string(baseline_artifact.get("replay_final_status"), "baseline replay_final_status")
    current_action = _require_non_empty_string(current_artifact.get("replay_enforcement_action"), "current replay_enforcement_action")
    baseline_action = _require_non_empty_string(baseline_artifact.get("replay_enforcement_action"), "baseline replay_enforcement_action")
    current_consistency = _require_non_empty_string(current_artifact.get("consistency_status"), "current consistency_status")
    baseline_consistency = _require_non_empty_string(baseline_artifact.get("consistency_status"), "baseline consistency_status")

    current_drift_detected = current_artifact.get("drift_detected")
    baseline_drift_detected = baseline_artifact.get("drift_detected")
    if not isinstance(current_drift_detected, bool) or not isinstance(baseline_drift_detected, bool):
        raise DriftDetectionError("current/baseline drift_detected must be boolean")

    current_failure = current_artifact.get("failure_reason")
    baseline_failure = baseline_artifact.get("failure_reason")

    return {
        "final_status_delta": float(1 if current_status != baseline_status else 0),
        "enforcement_action_delta": float(1 if current_action != baseline_action else 0),
        "consistency_mismatch_delta": float(1 if current_consistency != baseline_consistency else 0),
        "drift_detected_delta": float(1 if current_drift_detected != baseline_drift_detected else 0),
        "failure_reason_present_delta": float(
            1 if bool(current_failure) != bool(baseline_failure) else 0
        ),
    }


def build_drift_detection_result(
    current_artifact: Dict[str, Any],
    baseline_artifact: Dict[str, Any],
    policy: Dict[str, Any],
    *,
    trace_id: str | None = None,
    run_id: str | None = None,
) -> Dict[str, Any]:
    """Build a deterministic drift_detection_result artifact.

    Compares two replay_result artifacts against a governed baseline gate policy.
    """
    if not isinstance(current_artifact, dict) or not isinstance(baseline_artifact, dict):
        raise DriftDetectionError("current_artifact and baseline_artifact must be objects")

    current_input = deepcopy(current_artifact)
    baseline_input = deepcopy(baseline_artifact)

    _validate_or_raise(current_input, "replay_result", context="current replay_result")
    _validate_or_raise(baseline_input, "replay_result", context="baseline replay_result")

    current_type = current_input.get("artifact_type")
    baseline_type = baseline_input.get("artifact_type")
    if current_type != baseline_type:
        raise DriftDetectionError("comparison target artifact types must match")
    if current_type != "replay_result":
        raise DriftDetectionError("unsupported comparison target type")

    thresholds = _policy_dimension_thresholds(policy)
    policy_id = _require_non_empty_string(policy.get("policy_id"), "policy_id")
    baseline_source = _require_non_empty_string(policy.get("required_baseline_source"), "required_baseline_source")

    resolved_trace_id = trace_id or current_input.get("trace_id")
    resolved_run_id = run_id or current_input.get("replay_run_id")
    timestamp = _require_non_empty_string(current_input.get("timestamp"), "current timestamp")
    baseline_id = _require_non_empty_string(baseline_input.get("replay_id"), "baseline replay_id")
    comparison_target_id = _require_non_empty_string(current_input.get("replay_id"), "current replay_id")

    metrics = _extract_metrics(current_input, baseline_input)

    triggered: List[Dict[str, Any]] = []
    reasons: List[str] = []
    for dimension in _ALLOWED_DIMENSIONS:
        value = float(metrics[dimension])
        warn_threshold = thresholds[dimension]["warn"]
        block_threshold = thresholds[dimension]["block"]
        if value > block_threshold:
            triggered.append(
                {
                    "dimension": dimension,
                    "severity": "block",
                    "value": value,
                    "threshold": block_threshold,
                }
            )
            reasons.append(f"block threshold exceeded for {dimension}")
        elif value > warn_threshold:
            triggered.append(
                {
                    "dimension": dimension,
                    "severity": "warn",
                    "value": value,
                    "threshold": warn_threshold,
                }
            )
            reasons.append(f"warn threshold exceeded for {dimension}")

    if any(item["severity"] == "block" for item in triggered):
        drift_status = "exceeds_threshold"
    elif triggered:
        drift_status = "within_threshold"
    else:
        drift_status = "no_drift"
        reasons = ["no drift dimensions exceeded configured thresholds"]

    preimage = {
        "timestamp": timestamp,
        "trace_id": resolved_trace_id,
        "run_id": resolved_run_id,
        "policy_id": policy_id,
        "baseline_id": baseline_id,
        "comparison_target_id": comparison_target_id,
        "drift_status": drift_status,
        "metrics": metrics,
        "triggered_thresholds": triggered,
    }
    result = {
        "artifact_id": _stable_artifact_id(preimage),
        "artifact_type": "drift_detection_result",
        "schema_version": "1.1.0",
        "timestamp": timestamp,
        "trace_refs": {"trace_id": _require_non_empty_string(resolved_trace_id, "trace_id")},
        "run_id": _require_non_empty_string(resolved_run_id, "run_id"),
        "policy_id": policy_id,
        "baseline_id": baseline_id,
        "baseline_source": baseline_source,
        "comparison_target_id": comparison_target_id,
        "comparison_target_type": "replay_result",
        "drift_status": drift_status,
        "compared_dimensions": list(_ALLOWED_DIMENSIONS),
        "metrics": metrics,
        "triggered_thresholds": triggered,
        "reasons": reasons,
        "generated_by_version": _GENERATED_BY_VERSION,
    }

    _validate_or_raise(result, "drift_detection_result", context="drift_detection_result")
    return result
