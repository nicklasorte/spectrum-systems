"""Unified deterministic control-loop engine for governed signal inputs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.evaluation_control import (
    build_evaluation_control_decision,
)


class ControlLoopError(Exception):
    """Raised when control-loop evaluation cannot produce a governed decision."""


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate(instance: Any, schema: Dict[str, Any]) -> List[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    return [e.message for e in errors]


def _normalize_signal(artifact: Dict[str, Any]) -> Dict[str, Any]:
    artifact_type = artifact.get("artifact_type")
    if artifact_type != "replay_result":
        raise ControlLoopError(f"unsupported artifact_type for control loop: {artifact_type}")
    source_artifact_id = str(artifact.get("replay_id") or "")
    decision_inputs = {
        "consistency_status": artifact.get("consistency_status"),
        "has_observability_metrics": isinstance(artifact.get("observability_metrics"), dict),
        "has_error_budget_status": isinstance(artifact.get("error_budget_status"), dict),
    }

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
        "decision_inputs": decision_inputs,
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


def _evaluate_signal(
    signal: Dict[str, Any],
    artifact: Dict[str, Any],
) -> Dict[str, Any]:
    signal_type = signal["signal_type"]

    if signal_type == "replay_result":
        return build_evaluation_control_decision(artifact)

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
            "signal_type": {"type": "string", "enum": ["replay_result"]},
            "evaluation_path": {
                "type": "string",
                "enum": ["evaluation_control_from_replay_result"],
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

    decision = _evaluate_signal(signal, artifact)
    decision_schema = load_schema("evaluation_control_decision")
    decision_errors = _validate(decision, decision_schema)
    if decision_errors:
        raise ControlLoopError(
            "evaluation_control_decision failed schema validation: " + "; ".join(decision_errors)
        )

    control_trace = {
        "trace_id": decision["trace_id"],
        "run_id": decision["run_id"],
        "input_artifact_id": signal["source_artifact_id"],
        "signal_type": signal["signal_type"],
        "evaluation_path": (
            "evaluation_control_from_replay_result"
        ),
        "decision": decision["decision"],
        "timestamp": _now_iso(),
    }
    _validate_control_trace(control_trace)

    return {
        "evaluation_control_decision": decision,
        "control_trace": control_trace,
    }
