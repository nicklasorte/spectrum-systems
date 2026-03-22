"""Deterministic failure_eval_case generation for blocked runtime outcomes."""

from __future__ import annotations

from typing import Any, Dict
from uuid import NAMESPACE_URL, uuid5

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema


class EvalCaseGenerationError(ValueError):
    """Raised when a failure_eval_case cannot be generated deterministically."""


def _validate_failure_eval_case(artifact: Dict[str, Any]) -> None:
    schema = load_schema("failure_eval_case")
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(artifact)


def _derive_failure_mode(integration_result: Dict[str, Any]) -> str:
    status = str(integration_result.get("execution_status") or "blocked")
    actions = integration_result.get("execution_result", {}).get("actions_taken") or []

    if any((a.get("status") == "indeterminate") for a in actions if isinstance(a, dict)):
        return "indeterminate"
    if integration_result.get("publication_blocked") or integration_result.get("decision_blocked"):
        return "threshold_breach"
    if status in {"blocked", "repair_required", "escalated"}:
        return "threshold_breach"
    return "runtime_failure"


def generate_eval_case_from_failure(
    context: Dict[str, Any],
    integration_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate a deterministic failure_eval_case from blocked runtime execution."""
    if not isinstance(context, dict):
        raise EvalCaseGenerationError("context must be a dict")
    if not isinstance(integration_result, dict):
        raise EvalCaseGenerationError("integration_result must be a dict")

    if bool(integration_result.get("continuation_allowed")):
        raise EvalCaseGenerationError("cannot generate failure_eval_case when continuation is allowed")

    artifact = context.get("artifact")
    if not isinstance(artifact, dict):
        raise EvalCaseGenerationError("context.artifact must be a dict")

    source_trace_id = str(
        artifact.get("trace_id")
        or integration_result.get("execution_id")
        or "00000000-0000-4000-8000-000000000000"
    )
    deterministic_trace_id = str(uuid5(NAMESPACE_URL, f"failure-eval-case:{source_trace_id}"))
    eval_case_id = f"failure-eval-case-{uuid5(NAMESPACE_URL, f'failure-case-id:{source_trace_id}').hex[:12]}"

    failure_mode = _derive_failure_mode(integration_result)
    artifact_id = artifact.get("artifact_id") or artifact.get("evaluation_id") or source_trace_id

    generated = {
        "artifact_type": "failure_eval_case",
        "schema_version": "1.0.0",
        "trace_id": deterministic_trace_id,
        "eval_case_id": eval_case_id,
        "input_artifact_refs": [f"artifact://runtime/failure/{artifact_id}"],
        "expected_output_spec": {
            "failure_mode": failure_mode,
            "execution_status": str(integration_result.get("execution_status") or "blocked"),
            "required_response": "block_and_escalate",
        },
        "scoring_rubric": {
            "weights": {
                "corrective_action_completeness": 0.7,
                "reproducibility": 0.3,
            },
            "pass_threshold": 1.0,
        },
        "evaluation_type": "deterministic",
        "created_from": "failure_trace",
    }

    try:
        _validate_failure_eval_case(generated)
    except Exception as exc:  # pragma: no cover - explicit fail-closed boundary
        raise EvalCaseGenerationError(f"generated artifact failed failure_eval_case validation: {exc}") from exc

    return generated
