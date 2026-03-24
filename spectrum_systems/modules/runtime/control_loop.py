"""Unified deterministic control-loop engine for governed signal inputs."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.evaluation_control import (
    DEFAULT_THRESHOLDS,
    build_evaluation_control_decision,
)


class ControlLoopError(Exception):
    """Raised when control-loop evaluation cannot produce a governed decision."""


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _deterministic_id(prefix: str, payload: Dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def _validate(instance: Any, schema: Dict[str, Any]) -> List[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    return [e.message for e in errors]


def _normalize_signal(artifact: Dict[str, Any]) -> Dict[str, Any]:
    artifact_type = artifact.get("artifact_type")
    if artifact_type not in {"eval_summary", "failure_eval_case"}:
        raise ControlLoopError(f"unsupported artifact_type for control loop: {artifact_type}")

    if artifact_type == "eval_summary":
        source_artifact_id = str(artifact.get("eval_run_id") or "")
        decision_inputs = {
            "pass_rate": artifact.get("pass_rate"),
            "drift_rate": artifact.get("drift_rate"),
            "reproducibility_score": artifact.get("reproducibility_score"),
            "indeterminate_failure_count": artifact.get("indeterminate_failure_count", 0),
        }
    else:
        source_artifact_id = str(artifact.get("eval_case_id") or "")
        decision_inputs = {
            "evaluation_type": artifact.get("evaluation_type"),
            "created_from": artifact.get("created_from"),
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
        "run_id": str(artifact.get("eval_run_id") or artifact.get("source_run_id") or source_artifact_id or ""),
        "artifact_type": artifact_type,
    }


def _validate_normalized_signal(signal: Dict[str, Any]) -> None:
    required = ("signal_type", "source_artifact_id", "trace_id", "run_id")
    for key in required:
        value = signal.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ControlLoopError(f"normalized signal missing required field: {key}")


def _evaluate_signal(
    signal: Dict[str, Any],
    artifact: Dict[str, Any],
) -> Dict[str, Any]:
    signal_type = signal["signal_type"]

    if signal_type == "eval_summary":
        return build_evaluation_control_decision(artifact)

    if signal_type == "failure_eval_case":
        if not isinstance(signal.get("source_artifact_id"), str) or not signal["source_artifact_id"]:
            raise ControlLoopError("failure_eval_case missing eval_case_id for deterministic identity")
        if not isinstance(signal.get("run_id"), str) or not signal["run_id"]:
            raise ControlLoopError("failure_eval_case missing run_id for deterministic identity")
        if not isinstance(signal.get("trace_id"), str) or not signal["trace_id"]:
            raise ControlLoopError("failure_eval_case missing trace_id for deterministic identity")

        deterministic_identity_payload = {
            "artifact_type": "evaluation_control_decision",
            "schema_version": "1.1.0",
            "signal_type": "failure_eval_case",
            "run_id": signal["run_id"],
            "trace_id": signal["trace_id"],
            "source_artifact_id": signal["source_artifact_id"],
            "evaluation_type": signal["decision_inputs"].get("evaluation_type"),
            "created_from": signal["decision_inputs"].get("created_from"),
            "decision": "deny",
            "rationale_code": "deny_failure_eval_case",
        }
        decision = {
            "artifact_type": "evaluation_control_decision",
            "schema_version": "1.1.0",
            "decision_id": _deterministic_id("ECD", deterministic_identity_payload),
            "eval_run_id": signal["run_id"],
            "system_status": "blocked",
            "system_response": "block",
            "triggered_signals": ["indeterminate_failure"],
            "threshold_snapshot": {
                "reliability_threshold": DEFAULT_THRESHOLDS["reliability_threshold"],
                "drift_threshold": DEFAULT_THRESHOLDS["drift_threshold"],
                "trust_threshold": DEFAULT_THRESHOLDS["trust_threshold"],
            },
            "trace_id": signal["trace_id"],
            "created_at": _now_iso(),
            "decision": "deny",
            "rationale_code": "deny_failure_eval_case",
            "input_signal_reference": {
                "signal_type": "failure_eval_case",
                "source_artifact_id": signal["source_artifact_id"],
            },
            "run_id": signal["run_id"],
        }
        return decision

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
            "signal_type": {"type": "string", "enum": ["eval_summary", "failure_eval_case"]},
            "evaluation_path": {
                "type": "string",
                "enum": [
                    "evaluation_control_from_eval_summary",
                    "failure_eval_case_auto_deny",
                ],
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
            "evaluation_control_from_eval_summary"
            if signal["signal_type"] == "eval_summary"
            else "failure_eval_case_auto_deny"
        ),
        "decision": decision["decision"],
        "timestamp": _now_iso(),
    }
    _validate_control_trace(control_trace)

    return {
        "evaluation_control_decision": decision,
        "control_trace": control_trace,
    }
