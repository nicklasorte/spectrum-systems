"""Drift Detection Engine (BAH).

Deterministically classifies replay drift for BAG replay_result artifacts.
Fail-closed behavior is enforced: malformed input or unknown values raise
DriftDetectionError.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Dict, List

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema

_COMPARISON_FIELDS: List[str] = ["final_status", "enforcement_action"]
_ALLOWED_STATUSES = {"allow", "deny", "require_review"}
_ALLOWED_ACTIONS = {"allow_execution", "deny_execution", "require_manual_review"}


class DriftDetectionError(Exception):
    """Raised when drift detection cannot execute safely (fail-closed)."""


def _validate_or_raise(payload: Dict[str, Any], schema_name: str, *, context: str) -> None:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise DriftDetectionError(f"{context} failed validation: {details}")


def _stable_drift_id(source_run_id: str, replay_run_id: str, drift_type: str) -> str:
    payload = {
        "source_run_id": source_run_id,
        "replay_run_id": replay_run_id,
        "drift_type": drift_type,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_known_values(status: Any, action: Any, *, label: str) -> None:
    if status is not None and status not in _ALLOWED_STATUSES:
        raise DriftDetectionError(f"unknown {label} final_status value: {status}")
    if action is not None and action not in _ALLOWED_ACTIONS:
        raise DriftDetectionError(f"unknown {label} enforcement_action value: {action}")


def _build_result(
    *,
    source_run_id: str,
    replay_run_id: str,
    trace_id: str,
    detection_timestamp: str,
    original_values: Dict[str, Any],
    replay_values: Dict[str, Any],
    drift_type: str,
    drift_detected: bool,
    drift_severity: str,
) -> Dict[str, Any]:
    result = {
        "drift_result_id": _stable_drift_id(source_run_id, replay_run_id, drift_type),
        "source_run_id": source_run_id,
        "replay_run_id": replay_run_id,
        "drift_detected": drift_detected,
        "drift_type": drift_type,
        "comparison_fields": list(_COMPARISON_FIELDS),
        "original_values": dict(original_values),
        "replay_values": dict(replay_values),
        "drift_severity": drift_severity,
        "detection_timestamp": detection_timestamp,
        "provenance": {
            "trace_id": trace_id,
            "run_id": replay_run_id,
        },
    }
    _validate_or_raise(result, "drift_result", context="drift_result")
    return result


def detect_drift(replay_result: dict) -> dict:
    """Detect deterministic drift from a validated replay_result artifact."""
    if not isinstance(replay_result, dict):
        raise DriftDetectionError("replay_result must be an object")

    replay_input = deepcopy(replay_result)

    source_run_id = replay_input.get("original_run_id")
    replay_run_id = replay_input.get("replay_run_id")
    trace_id = replay_input.get("trace_id")
    detection_timestamp = replay_input.get("timestamp")
    consistency_status = replay_input.get("consistency_status")

    required = {
        "original_run_id": source_run_id,
        "replay_run_id": replay_run_id,
        "trace_id": trace_id,
        "timestamp": detection_timestamp,
        "consistency_status": consistency_status,
    }
    missing = [key for key, value in required.items() if not isinstance(value, str) or not value]
    if missing:
        raise DriftDetectionError(f"replay_result missing required fields: {missing}")

    # Missing comparison surfaces are classified before full schema validation.
    original_keys_present = all(
        key in replay_input for key in ("original_final_status", "original_enforcement_action")
    )
    replay_keys_present = all(
        key in replay_input for key in ("replay_final_status", "replay_enforcement_action")
    )

    if not original_keys_present:
        original_values = {
            "final_status": replay_input.get("original_final_status"),
            "enforcement_action": replay_input.get("original_enforcement_action"),
        }
        replay_values = {
            "final_status": replay_input.get("replay_final_status"),
            "enforcement_action": replay_input.get("replay_enforcement_action"),
        }
        return _build_result(
            source_run_id=source_run_id,
            replay_run_id=replay_run_id,
            trace_id=trace_id,
            detection_timestamp=detection_timestamp,
            original_values=original_values,
            replay_values=replay_values,
            drift_type="missing_original",
            drift_detected=True,
            drift_severity="critical",
        )

    if not replay_keys_present:
        original_values = {
            "final_status": replay_input.get("original_final_status"),
            "enforcement_action": replay_input.get("original_enforcement_action"),
        }
        replay_values = {
            "final_status": replay_input.get("replay_final_status"),
            "enforcement_action": replay_input.get("replay_enforcement_action"),
        }
        return _build_result(
            source_run_id=source_run_id,
            replay_run_id=replay_run_id,
            trace_id=trace_id,
            detection_timestamp=detection_timestamp,
            original_values=original_values,
            replay_values=replay_values,
            drift_type="missing_replay",
            drift_detected=True,
            drift_severity="critical",
        )

    _validate_or_raise(replay_input, "replay_result", context="replay_result")

    original_values = {
        "final_status": replay_input.get("original_final_status"),
        "enforcement_action": replay_input.get("original_enforcement_action"),
    }
    replay_values = {
        "final_status": replay_input.get("replay_final_status"),
        "enforcement_action": replay_input.get("replay_enforcement_action"),
    }

    _validate_known_values(original_values["final_status"], original_values["enforcement_action"], label="original")
    _validate_known_values(replay_values["final_status"], replay_values["enforcement_action"], label="replay")

    if any(value is None for value in original_values.values()):
        return _build_result(
            source_run_id=source_run_id,
            replay_run_id=replay_run_id,
            trace_id=trace_id,
            detection_timestamp=detection_timestamp,
            original_values=original_values,
            replay_values=replay_values,
            drift_type="missing_original",
            drift_detected=True,
            drift_severity="critical",
        )

    if any(value is None for value in replay_values.values()):
        return _build_result(
            source_run_id=source_run_id,
            replay_run_id=replay_run_id,
            trace_id=trace_id,
            detection_timestamp=detection_timestamp,
            original_values=original_values,
            replay_values=replay_values,
            drift_type="missing_replay",
            drift_detected=True,
            drift_severity="critical",
        )

    if consistency_status == "indeterminate":
        return _build_result(
            source_run_id=source_run_id,
            replay_run_id=replay_run_id,
            trace_id=trace_id,
            detection_timestamp=detection_timestamp,
            original_values=original_values,
            replay_values=replay_values,
            drift_type="indeterminate",
            drift_detected=True,
            drift_severity="high",
        )

    if consistency_status not in {"match", "mismatch"}:
        raise DriftDetectionError(f"unknown consistency_status value: {consistency_status}")

    if original_values["final_status"] != replay_values["final_status"]:
        return _build_result(
            source_run_id=source_run_id,
            replay_run_id=replay_run_id,
            trace_id=trace_id,
            detection_timestamp=detection_timestamp,
            original_values=original_values,
            replay_values=replay_values,
            drift_type="status_mismatch",
            drift_detected=True,
            drift_severity="high",
        )

    if original_values["enforcement_action"] != replay_values["enforcement_action"]:
        return _build_result(
            source_run_id=source_run_id,
            replay_run_id=replay_run_id,
            trace_id=trace_id,
            detection_timestamp=detection_timestamp,
            original_values=original_values,
            replay_values=replay_values,
            drift_type="action_mismatch",
            drift_detected=True,
            drift_severity="medium",
        )

    return _build_result(
        source_run_id=source_run_id,
        replay_run_id=replay_run_id,
        trace_id=trace_id,
        detection_timestamp=detection_timestamp,
        original_values=original_values,
        replay_values=replay_values,
        drift_type="none",
        drift_detected=False,
        drift_severity="none",
    )


def validate_drift_result(result: Dict[str, Any]) -> List[str]:
    """Validate drift_result payloads against the canonical schema."""
    try:
        schema = load_schema("drift_result")
    except (OSError, FileNotFoundError, ValueError) as exc:
        return [f"validate_drift_result: schema unavailable: {exc}"]

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(result), key=lambda e: list(e.path))
    return [e.message for e in errors]


def validate_replay_artifact(artifact: Dict[str, Any]) -> List[str]:
    """Backward-compatible replay_result validator used by runtime package exports."""
    try:
        _validate_or_raise(artifact, "replay_result", context="replay_result")
    except DriftDetectionError as exc:
        return [str(exc)]
    return []


def run_drift_detection(replay_artifact: Dict[str, Any], baseline_artifact: Dict[str, Any] | None = None, config: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Compatibility alias retained for prior callers.

    baseline_artifact/config are unsupported for governed BAH output and will
    fail-closed when provided.
    """
    if baseline_artifact is not None or config is not None:
        raise DriftDetectionError("run_drift_detection no longer accepts baseline_artifact/config")
    return detect_drift(replay_artifact)


def validate_drift_detection_result(result: Dict[str, Any]) -> List[str]:
    """Backward-compatible alias for drift_result validation."""
    return validate_drift_result(result)
