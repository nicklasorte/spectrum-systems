"""Deterministic failure → eval_case artifact auto-generation (Prompt BBB)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class EvalCaseGenerationError(Exception):
    """Raised when eval_case generation fails closed."""


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _validate_eval_case(eval_case: Dict[str, Any]) -> None:
    schema = load_schema("eval_case")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(eval_case), key=lambda e: list(e.absolute_path))
    if errors:
        messages = "; ".join(e.message for e in errors)
        raise EvalCaseGenerationError(f"eval_case schema validation failed: {messages}")


def _detect_failure_mode(artifact: Dict[str, Any], execution_result: Dict[str, Any]) -> str:
    status = execution_result.get("status")
    if status == "error":
        return "execution_failure"
    if status == "indeterminate":
        return "indeterminate"

    if artifact.get("artifact_type") == "eval_summary" and artifact.get("decision") != "allow":
        return "threshold_breach"

    if execution_result.get("drift_signal") is not None or artifact.get("drift_signal") is not None:
        return "drift_detected"

    validators_failed = execution_result.get("validators_failed") or []
    if execution_result.get("schema_validation_failed") is True:
        return "schema_violation"
    if status == "schema_violation":
        return "schema_violation"
    if any(isinstance(v, str) and "schema" in v for v in validators_failed):
        return "schema_violation"

    if status in {"deny", "require_review"}:
        return "execution_failure"

    raise EvalCaseGenerationError("unable to determine failure_mode from structured inputs")


def _extract_input_snapshot(artifact: Dict[str, Any]) -> Dict[str, Any]:
    key_metrics: Dict[str, Any] = {}
    for metric in ("pass_rate", "drift_rate", "reproducibility_score"):
        if metric in artifact:
            key_metrics[metric] = artifact[metric]

    decision_inputs: Dict[str, Any] = {}
    for key in (
        "pass_rate",
        "drift_rate",
        "reproducibility_score",
        "indeterminate_failure_count",
        "indeterminate_count",
        "decision",
    ):
        if key in artifact:
            decision_inputs[key] = artifact[key]

    return {
        "artifact_type": artifact.get("artifact_type") or artifact.get("type") or "runtime_artifact",
        "key_metrics": key_metrics,
        "decision_inputs": decision_inputs,
    }


def _derive_observed_behavior(execution_result: Dict[str, Any]) -> str:
    observed = execution_result.get("status")
    if observed in {"allow", "deny", "require_review", "indeterminate"}:
        return observed
    if observed in {"error", "schema_violation"}:
        return "deny"

    execution_status = execution_result.get("execution_status")
    if execution_status in {"blocked", "repair_required", "escalated", "error"}:
        return "deny"
    if execution_status == "success":
        if bool(execution_result.get("human_review_required", False)):
            return "require_review"
        return "allow"

    raise EvalCaseGenerationError("execution_result missing observed behavior status")


def _build_reproducibility(artifact: Dict[str, Any]) -> Dict[str, Any]:
    if "seed" in artifact:
        return {
            "deterministic": False,
            "requires_seed": True,
            "seed_value": artifact.get("seed"),
        }
    return {
        "deterministic": True,
        "requires_seed": False,
        "seed_value": None,
    }


def generate_eval_case_from_failure(
    artifact: dict,
    execution_result: dict,
    trace_context: dict,
) -> dict:
    """Generate a governed eval_case artifact from deterministic failure signals."""
    if not isinstance(artifact, dict):
        raise EvalCaseGenerationError("artifact must be a dict")
    if not isinstance(execution_result, dict):
        raise EvalCaseGenerationError("execution_result must be a dict")
    if not isinstance(trace_context, dict):
        raise EvalCaseGenerationError("trace_context must be a dict")

    source_artifact_type = artifact.get("artifact_type") or artifact.get("type") or "runtime_artifact"
    source_artifact_id = (
        artifact.get("artifact_id")
        or artifact.get("eval_run_id")
        or artifact.get("evaluation_id")
        or trace_context.get("run_id")
    )
    trace_id = trace_context.get("trace_id") or artifact.get("trace_id") or trace_context.get("run_id")
    run_id = trace_context.get("run_id")

    missing: List[str] = []
    if not source_artifact_id:
        missing.append("source_artifact_id")
    if not trace_id:
        missing.append("trace_id")
    if not run_id:
        missing.append("run_id")
    if missing:
        raise EvalCaseGenerationError(f"missing required fields: {', '.join(missing)}")

    eval_case = {
        "eval_case_id": str(uuid.uuid4()),
        "source_artifact_type": source_artifact_type,
        "source_artifact_id": str(source_artifact_id),
        "failure_mode": _detect_failure_mode(artifact, execution_result),
        "input_snapshot": _extract_input_snapshot(artifact),
        "expected_behavior": "deny",
        "observed_behavior": _derive_observed_behavior(execution_result),
        "generation_timestamp": _now_iso(),
        "provenance": {
            "trace_id": str(trace_id),
            "run_id": str(run_id),
        },
        "reproducibility": _build_reproducibility(artifact),
    }

    _validate_eval_case(eval_case)
    return eval_case
