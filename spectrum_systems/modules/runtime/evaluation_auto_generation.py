"""AG-05 deterministic failure_eval_case generation from governed failure/control artifacts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.utils.deterministic_id import deterministic_id


class EvalCaseGenerationError(ValueError):
    """Raised when a failure_eval_case cannot be generated deterministically."""


_IN_SCOPE_SOURCE_TYPES = frozenset(
    {
        "agent_failure_record",
        "hitl_review_request",
        "evaluation_control_decision",
    }
)


def _validate_failure_eval_case(artifact: Dict[str, Any]) -> None:
    schema = load_schema("failure_eval_case")
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(artifact)


def _deterministic_timestamp(seed_payload: Dict[str, Any]) -> str:
    canonical = json.dumps(seed_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    offset_seconds = int(digest[:8], 16) % (365 * 24 * 60 * 60)
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return (base + timedelta(seconds=offset_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _string(value: Any, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise EvalCaseGenerationError(f"{field} must be a non-empty string")
    return text


def _source_identity(source_artifact: Dict[str, Any]) -> Tuple[str, str, str]:
    source_artifact_type = _string(source_artifact.get("artifact_type"), field="source artifact_type")
    if source_artifact_type not in _IN_SCOPE_SOURCE_TYPES:
        raise EvalCaseGenerationError(
            f"unsupported source artifact_type '{source_artifact_type}' for AG-05 auto-generation"
        )

    source_artifact_id = str(
        source_artifact.get("id")
        or source_artifact.get("decision_id")
        or source_artifact.get("eval_run_id")
        or source_artifact.get("override_decision_id")
        or source_artifact.get("artifact_id")
        or ""
    ).strip()
    if not source_artifact_id:
        raise EvalCaseGenerationError("source artifact missing deterministic artifact id")

    trace_id = _string(source_artifact.get("trace_id"), field="source trace_id")
    return source_artifact_type, source_artifact_id, trace_id


def _condition_tuple(
    source_artifact: Dict[str, Any],
    execution_result: Optional[Dict[str, Any]],
) -> Tuple[str, str, str, str, str, str]:
    source_type = source_artifact["artifact_type"]

    if source_type == "agent_failure_record":
        return (
            "runtime_failure",
            "runtime_boundary",
            "governed_runtime_failure_artifact",
            "system_must_fail_closed_and_emit_failure_artifact",
            "runtime_failed_with_governed_failure_artifact",
            "controller_must_deny_and_require_remediation",
        )

    if source_type == "hitl_review_request":
        trigger_reason = str(source_artifact.get("trigger_reason") or "")
        if trigger_reason not in {
            "indeterminate_outcome_routed_to_human",
            "policy_review_required",
            "control_non_allow_response",
        }:
            raise EvalCaseGenerationError(
                f"unsupported hitl_review_request trigger_reason '{trigger_reason}' for AG-05"
            )
        return (
            "review_boundary_halt",
            "review_boundary",
            f"review_required_halt:{trigger_reason}",
            "system_must_remain_blocked_pending_review_or_override",
            "review_required_halt_emitted",
            "controller_must_deny_until_review_resolution",
        )

    if source_type == "evaluation_control_decision":
        decision = str(source_artifact.get("decision") or "")
        rationale_code = str(source_artifact.get("rationale_code") or "")
        if decision not in {"deny", "require_review"}:
            raise EvalCaseGenerationError(
                "evaluation_control_decision must be deny/require_review for AG-05 auto-generation"
            )
        if decision == "require_review" and "indeterminate" not in rationale_code:
            raise EvalCaseGenerationError(
                "evaluation_control_decision require_review must be indeterminate-class for AG-05"
            )
        return (
            "control_indeterminate" if decision == "require_review" else "runtime_failure",
            "control_boundary",
            f"control_decision:{decision}:{rationale_code or 'unspecified'}",
            "system_must_not_allow_progression_when_control_non_allow",
            f"control_decision_emitted:{decision}",
            "controller_must_deny_and_link_to_source_decision",
        )

    raise EvalCaseGenerationError(f"unsupported source artifact_type '{source_type}'")


def generate_failure_eval_case(
    *,
    source_artifact: Dict[str, Any],
    source_run_id: str,
    stage: str,
    runtime_environment: str,
    execution_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate AG-05 failure_eval_case from a bounded governed source artifact."""
    if not isinstance(source_artifact, dict):
        raise EvalCaseGenerationError("source_artifact must be a dict")
    if execution_result is not None and not isinstance(execution_result, dict):
        raise EvalCaseGenerationError("execution_result must be a dict when provided")

    source_artifact_type, source_artifact_id, trace_id = _source_identity(source_artifact)
    source_run = _string(source_run_id, field="source_run_id")

    (
        failure_class,
        failure_stage,
        triggering_condition,
        expected_system_behavior,
        observed_system_behavior,
        evaluation_goal,
    ) = _condition_tuple(source_artifact, execution_result)

    identity_payload = {
        "source_run_id": source_run,
        "trace_id": trace_id,
        "source_artifact_type": source_artifact_type,
        "source_artifact_id": source_artifact_id,
        "failure_class": failure_class,
        "failure_stage": failure_stage,
        "triggering_condition": triggering_condition,
        "stage": stage,
        "runtime_environment": runtime_environment,
    }

    artifact = {
        "artifact_type": "failure_eval_case",
        "schema_version": "1.1.0",
        "eval_case_id": deterministic_id(
            prefix="fec",
            namespace="ag05_failure_eval_case",
            payload=identity_payload,
        ),
        "created_at": _deterministic_timestamp(identity_payload),
        "source_run_id": source_run,
        "trace_id": trace_id,
        "source_artifact_type": source_artifact_type,
        "source_artifact_id": source_artifact_id,
        "failure_class": failure_class,
        "failure_stage": failure_stage,
        "triggering_condition": triggering_condition,
        "normalized_inputs": {
            "stage": _string(stage, field="stage"),
            "runtime_environment": _string(runtime_environment, field="runtime_environment"),
            "continuation_allowed": bool((execution_result or {}).get("continuation_allowed", False)),
            "publication_blocked": bool((execution_result or {}).get("publication_blocked", True)),
            "decision_blocked": bool((execution_result or {}).get("decision_blocked", True)),
            "human_review_required": bool((execution_result or {}).get("human_review_required", False)),
            "escalation_triggered": bool((execution_result or {}).get("escalation_triggered", False)),
        },
        "expected_system_behavior": expected_system_behavior,
        "observed_system_behavior": observed_system_behavior,
        "evaluation_goal": evaluation_goal,
        "pass_criteria": {
            "decision_must_remain_denied": True,
            "review_or_remediation_required": True,
            "replay_reproducible": True,
        },
        "provenance": {
            "source_artifact_ref": f"{source_artifact_type}:{source_artifact_id}",
            "generation_path": "ag_runtime_failure_eval_auto_generation",
            "generated_by_module": "spectrum_systems.modules.runtime.evaluation_auto_generation",
        },
    }

    try:
        _validate_failure_eval_case(artifact)
    except Exception as exc:  # pragma: no cover - explicit fail-closed boundary
        raise EvalCaseGenerationError(f"generated artifact failed failure_eval_case validation: {exc}") from exc
    return artifact


# Backwards-compatible alias for existing callers/tests.
def generate_eval_case_from_failure(context: Dict[str, Any], integration_result: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(context, dict):
        raise EvalCaseGenerationError("context must be a dict")
    if not isinstance(integration_result, dict):
        raise EvalCaseGenerationError("integration_result must be a dict")
    if bool(integration_result.get("continuation_allowed")):
        raise EvalCaseGenerationError("cannot generate failure_eval_case when continuation is allowed")

    artifact = context.get("artifact")
    if not isinstance(artifact, dict):
        raise EvalCaseGenerationError("context.artifact must be a dict")

    return generate_failure_eval_case(
        source_artifact=artifact,
        source_run_id=str(
            artifact.get("run_id")
            or artifact.get("eval_run_id")
            or integration_result.get("execution_id")
            or ""
        ),
        stage=str(context.get("stage") or "unknown"),
        runtime_environment=str(context.get("runtime_environment") or "unknown"),
        execution_result=integration_result,
    )
