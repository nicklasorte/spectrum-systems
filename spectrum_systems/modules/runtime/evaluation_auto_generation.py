"""AG-05 deterministic failure_eval_case generation from governed failure/control artifacts."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.utils.deterministic_id import deterministic_id


class EvalCaseGenerationError(ValueError):
    """Raised when a failure_eval_case cannot be generated deterministically."""


def canonical_json(obj: dict[str, Any]) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def dedupe_preserve_order(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


_IN_SCOPE_SOURCE_TYPES = frozenset(
    {
        "agent_failure_record",
        "hitl_review_request",
        "evaluation_control_decision",
    }
)

_FAILURE_CLASS_PREVENTION_MAP: Dict[str, Dict[str, Any]] = {
    "runtime_failure": {
        "prevention_action": "block_repeat_execution",
        "policy_suffix": "runtime_failure_repeat_block",
        "control_decision_surface": "evaluation_control_decision",
        "recurrence_scope_fields": ("failure_class_id", "failure_stage", "runtime_environment"),
    },
    "review_boundary_halt": {
        "prevention_action": "require_manual_review",
        "policy_suffix": "review_boundary_manual_gate",
        "control_decision_surface": "evaluation_control_decision",
        "recurrence_scope_fields": ("failure_class_id", "failure_stage", "runtime_environment"),
    },
    "control_indeterminate": {
        "prevention_action": "require_fix_before_progression",
        "policy_suffix": "control_indeterminate_fix_gate",
        "control_decision_surface": "evaluation_control_decision",
        "recurrence_scope_fields": ("failure_class_id", "failure_stage", "runtime_environment"),
    },
}


def _validate_failure_eval_case(artifact: Dict[str, Any]) -> None:
    schema = load_schema("failure_eval_case")
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(artifact)


def _validate_failure_pattern_record(artifact: Dict[str, Any]) -> None:
    schema = load_schema("failure_pattern_record")
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(artifact)


def _canonical_list(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        raise EvalCaseGenerationError("list-like input must be a list or string")
    normalized = [str(item).strip() for item in values if str(item).strip()]
    return dedupe_preserve_order(normalized)


def normalize_failure_pattern(
    *,
    stop_reason: str,
    root_cause_chain: list[dict[str, Any]],
    blocking_conditions: list[str],
) -> str:
    """Build a stable deterministic failure-pattern key."""
    resolved_stop = _string(stop_reason, field="stop_reason")
    if not isinstance(root_cause_chain, list):
        raise EvalCaseGenerationError("root_cause_chain must be a list")
    if not isinstance(blocking_conditions, list):
        raise EvalCaseGenerationError("blocking_conditions must be a list")
    normalized_chain = []
    for item in root_cause_chain:
        if not isinstance(item, dict):
            raise EvalCaseGenerationError("root_cause_chain entries must be objects")
        step = str(item.get("step") or "").strip() or "unknown_step"
        reason = str(item.get("reason") or "").strip() or "unknown_reason"
        normalized_chain.append({"step": step, "reason": reason})
    normalized_chain = sorted(normalized_chain, key=lambda item: (item["step"], item["reason"]))
    payload = {
        "stop_reason": resolved_stop,
        "root_cause_chain": normalized_chain,
        "blocking_conditions": _canonical_list(blocking_conditions),
    }
    return hashlib.sha256(canonical_json(payload)).hexdigest()


def build_failure_pattern_record(
    *,
    stop_reason: str,
    root_cause_chain: list[dict[str, Any]],
    blocking_conditions: list[str],
    trace_id: str,
    related_artifacts: Optional[list[str]] = None,
    prior_record: Optional[dict[str, Any]] = None,
    observed_at: Optional[str] = None,
) -> dict[str, Any]:
    normalized_key = normalize_failure_pattern(
        stop_reason=stop_reason,
        root_cause_chain=root_cause_chain,
        blocking_conditions=blocking_conditions,
    )
    timestamp = _string(observed_at or "1970-01-01T00:00:00Z", field="observed_at")
    prior = prior_record if isinstance(prior_record, dict) else {}
    occurrence_count = int(prior.get("occurrence_count", 0)) + 1
    trace_ids = _canonical_list(list(prior.get("trace_ids") or []) + [trace_id])
    stop_reasons = _canonical_list(list(prior.get("associated_stop_reasons") or []) + [stop_reason])
    root_causes = _canonical_list(
        list(prior.get("associated_root_causes") or [])
        + [f"{str(item.get('step') or '').strip()}:{str(item.get('reason') or '').strip()}" for item in root_cause_chain if isinstance(item, dict)]
    )
    related = _canonical_list(list(prior.get("related_artifacts") or []) + list(related_artifacts or []))
    record = {
        "artifact_type": "failure_pattern_record",
        "schema_version": "1.0.0",
        "pattern_id": deterministic_id(
            prefix="fpr",
            namespace="batch_l_failure_pattern_record",
            payload={"normalized_failure_key": normalized_key},
        ),
        "normalized_failure_key": normalized_key,
        "occurrence_count": occurrence_count,
        "first_seen": str(prior.get("first_seen") or timestamp),
        "last_seen": timestamp,
        "associated_stop_reasons": stop_reasons,
        "associated_root_causes": root_causes or ["unknown_step:unknown_reason"],
        "related_artifacts": related,
        "trace_ids": trace_ids,
    }
    _validate_failure_pattern_record(record)
    return record


def _deterministic_timestamp(seed_payload: Dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json(seed_payload)).hexdigest()
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


def register_failure_eval_case(
    *,
    failure_eval_case: Dict[str, Any],
    eval_registry: Dict[str, Dict[str, Any]],
    policy_id: str,
    trigger_condition: str,
    control_decision_surface: str = "evaluation_control_decision",
) -> Dict[str, Any]:
    """Register a failure_eval_case and return deterministic policy binding metadata.

    This is a fail-closed CL-01 seam: failure-derived evals must be both
    registry-tracked and policy-bound before they can influence control.
    """
    if not isinstance(eval_registry, dict):
        raise EvalCaseGenerationError("eval_registry must be a dict")
    if not isinstance(failure_eval_case, dict):
        raise EvalCaseGenerationError("failure_eval_case must be a dict")
    try:
        _validate_failure_eval_case(failure_eval_case)
    except Exception as exc:  # pragma: no cover - defensive boundary
        raise EvalCaseGenerationError(f"failure_eval_case failed validation before registration: {exc}") from exc

    eval_case_id = _string(failure_eval_case.get("eval_case_id"), field="failure_eval_case.eval_case_id")
    trace_id = _string(failure_eval_case.get("trace_id"), field="failure_eval_case.trace_id")
    failure_id = _string(failure_eval_case.get("source_artifact_id"), field="failure_eval_case.source_artifact_id")
    resolved_policy_id = _string(policy_id, field="policy_id")
    resolved_trigger = _string(trigger_condition, field="trigger_condition")
    decision_surface = _string(control_decision_surface, field="control_decision_surface")
    failure_class_id = _string(failure_eval_case.get("failure_class"), field="failure_eval_case.failure_class")
    mapping = _FAILURE_CLASS_PREVENTION_MAP.get(failure_class_id)
    if mapping is None:
        raise EvalCaseGenerationError(
            f"missing recurrence prevention mapping for governed failure_class_id '{failure_class_id}'"
        )

    stage = _string(failure_eval_case.get("failure_stage"), field="failure_eval_case.failure_stage")
    normalized_inputs = failure_eval_case.get("normalized_inputs")
    if not isinstance(normalized_inputs, dict):
        raise EvalCaseGenerationError("failure_eval_case.normalized_inputs must be an object")
    runtime_environment = _string(
        normalized_inputs.get("runtime_environment"),
        field="failure_eval_case.normalized_inputs.runtime_environment",
    )
    recurrence_scope = {
        "failure_class_id": failure_class_id,
        "failure_stage": stage,
        "runtime_environment": runtime_environment,
    }
    scope_fields = tuple(mapping.get("recurrence_scope_fields") or ())
    if not scope_fields:
        raise EvalCaseGenerationError("recurrence prevention mapping missing scope fields")

    resolved_rule_policy_id = f"{resolved_policy_id}::{mapping['policy_suffix']}"
    prevention_action = str(mapping["prevention_action"])
    prevention_rule_id = deterministic_id(
        prefix="rpr",
        namespace="cl03_recurrence_prevention_rule",
        payload={
            "failure_class_id": failure_class_id,
            "policy_id": resolved_rule_policy_id,
            "control_decision_surface": decision_surface,
            "scope": {field: recurrence_scope[field] for field in scope_fields},
            "prevention_action": prevention_action,
        },
    )
    recurrence_prevention_artifact = {
        "artifact_type": "recurrence_prevention_authority",
        "artifact_id": deterministic_id(
            prefix="rpa",
            namespace="cl03_recurrence_prevention_artifact",
            payload={
                "failure_class_id": failure_class_id,
                "eval_case_id": eval_case_id,
                "failure_id": failure_id,
                "trace_id": trace_id,
                "prevention_rule_id": prevention_rule_id,
            },
        ),
        "source_failure_class_id": failure_class_id,
        "source_failure_id": failure_id,
        "linked_eval_case_ids": [eval_case_id],
        "policy_id": resolved_rule_policy_id,
        "prevention_rule_id": prevention_rule_id,
        "prevention_action": prevention_action,
        "control_decision_surface": decision_surface,
        "recurrence_scope": {field: recurrence_scope[field] for field in scope_fields},
        "trace": {
            "trace_id": trace_id,
            "source_artifact_ref": f"{failure_eval_case.get('source_artifact_type')}:{failure_id}",
            "eval_case_ref": f"failure_eval_case:{eval_case_id}",
        },
    }

    binding_payload = {
        "eval_case_id": eval_case_id,
        "failure_id": failure_id,
        "trace_id": trace_id,
        "policy_id": resolved_rule_policy_id,
        "trigger_condition": resolved_trigger,
        "control_decision_surface": decision_surface,
        "failure_class_id": failure_class_id,
        "prevention_action": prevention_action,
        "prevention_rule_id": prevention_rule_id,
        "recurrence_scope": recurrence_prevention_artifact["recurrence_scope"],
        "recurrence_prevention_artifact": recurrence_prevention_artifact,
        "binding_id": deterministic_id(
            prefix="fcb",
            namespace="cl01_failure_eval_policy_binding",
            payload={
                "eval_case_id": eval_case_id,
                "trace_id": trace_id,
                "policy_id": resolved_rule_policy_id,
                "trigger_condition": resolved_trigger,
                "control_decision_surface": decision_surface,
                "prevention_rule_id": prevention_rule_id,
            },
        ),
    }
    eval_registry[eval_case_id] = binding_payload
    return dict(binding_payload)


def map_failure_class_to_prevention_rule(failure_class_id: str) -> Dict[str, str]:
    """Return deterministic recurrence-prevention mapping for a governed failure class."""
    key = _string(failure_class_id, field="failure_class_id")
    mapping = _FAILURE_CLASS_PREVENTION_MAP.get(key)
    if mapping is None:
        raise EvalCaseGenerationError(
            f"missing recurrence prevention mapping for governed failure_class_id '{key}'"
        )
    return {
        "failure_class_id": key,
        "prevention_action": str(mapping["prevention_action"]),
        "control_decision_surface": str(mapping["control_decision_surface"]),
        "recurrence_scope_fields": ",".join(mapping["recurrence_scope_fields"]),
    }


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


_REVIEW_FAMILY_PATTERN = re.compile(r"\[eval_family:([a-z0-9_\\-]+)\]", re.IGNORECASE)
_SUPPORTED_REVIEW_EVAL_FAMILIES = frozenset(
    {
        "review_gate_alignment",
        "review_scale_alignment",
        "review_critical_findings_presence",
        "review_signal_validity",
    }
)


def _extract_review_eval_family(finding_text: str) -> str:
    match = _REVIEW_FAMILY_PATTERN.search(finding_text)
    if match is None:
        raise EvalCaseGenerationError(
            "critical finding is missing explicit [eval_family:<family>] mapping; fail-closed to avoid ambiguous mapping"
        )
    family = match.group(1).lower()
    if family not in _SUPPORTED_REVIEW_EVAL_FAMILIES:
        raise EvalCaseGenerationError(f"unsupported review eval family mapping: {family}")
    return family




def build_review_eval_generation_report(*, generated_eval_cases: list[Dict[str, Any]], recurrence_counts: Dict[str, int], trace_id: str, high_priority_threshold: int = 3) -> Dict[str, Any]:
    if not isinstance(trace_id, str) or not trace_id:
        raise EvalCaseGenerationError("trace_id must be non-empty")
    records = []
    for key in sorted(recurrence_counts):
        count = int(recurrence_counts[key])
        records.append({
            "dedupe_key": key,
            "recurrence_count": count,
            "high_priority": count >= high_priority_threshold,
        })
    artifact = {
        "artifact_type": "review_eval_generation_report",
        "schema_version": "1.0.0",
        "report_id": deterministic_id(prefix="regr", namespace="review_eval_generation_report", payload={"trace_id": trace_id, "records": records}),
        "trace_id": trace_id,
        "generated_eval_count": len(generated_eval_cases),
        "high_priority_eval_count": sum(1 for item in records if item["high_priority"]),
        "recurrence_records": records,
    }
    Draft202012Validator(load_schema("review_eval_generation_report"), format_checker=FormatChecker()).validate(artifact)
    return artifact

def generate_failure_derived_eval_cases_from_review_signal(
    review_control_signal: Dict[str, Any],
    *,
    prior_recurrence_counts: Optional[Dict[str, int]] = None,
    high_priority_threshold: int = 3,
) -> list[Dict[str, Any]]:
    """Generate deterministic deduped eval_case artifacts from critical review findings."""
    if not isinstance(review_control_signal, dict):
        raise EvalCaseGenerationError("review_control_signal must be a dict")
    signal_schema = load_schema("review_control_signal")
    Draft202012Validator(signal_schema, format_checker=FormatChecker()).validate(review_control_signal)

    gate_assessment = str(review_control_signal.get("gate_assessment") or "")
    scale_recommendation = str(review_control_signal.get("scale_recommendation") or "")
    critical_findings = [str(item).strip() for item in (review_control_signal.get("critical_findings") or []) if str(item).strip()]
    should_generate = gate_assessment == "FAIL" or (
        gate_assessment == "CONDITIONAL" and bool(critical_findings)
    ) or (
        scale_recommendation == "NO" and bool(critical_findings)
    )
    if not should_generate:
        return []

    unique_findings = dedupe_preserve_order(critical_findings)
    artifacts: list[Dict[str, Any]] = []
    seen_eval_case_ids: set[str] = set()
    eval_case_schema = load_schema("eval_case")
    validator = Draft202012Validator(eval_case_schema, format_checker=FormatChecker())
    recurrence = dict(prior_recurrence_counts or {})

    for index, finding in enumerate(unique_findings, start=1):
        eval_family = _extract_review_eval_family(finding)
        normalized_finding = " ".join(finding.split())
        identity_payload = {
            "signal_id": review_control_signal.get("signal_id"),
            "review_id": review_control_signal.get("review_id"),
            "eval_family": eval_family,
            "finding": normalized_finding,
        }
        dedupe_key = deterministic_id(
            prefix="rfd",
            namespace="review_failure_dedupe_key",
            payload=identity_payload,
        )
        eval_case_id = deterministic_id(
            prefix="ec",
            namespace="review_failure_derived_eval_case",
            payload=identity_payload,
        )
        recurrence_count = int(recurrence.get(dedupe_key, 0)) + 1
        recurrence[dedupe_key] = recurrence_count
        if eval_case_id in seen_eval_case_ids:
            continue
        seen_eval_case_ids.add(eval_case_id)

        eval_case = {
            "artifact_type": "eval_case",
            "schema_version": "1.0.0",
            "run_id": deterministic_id(
                prefix="run",
                namespace="review_failure_derived_eval_case_run",
                payload=identity_payload,
            ),
            "trace_id": str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"review-failure-derived::{review_control_signal.get('signal_id')}::{eval_case_id}",
                )
            ),
            "eval_case_id": eval_case_id,
            "input_artifact_refs": [
                f"review_control_signal:{review_control_signal.get('signal_id')}",
                f"review:{review_control_signal.get('review_id')}",
            ],
            "expected_output_spec": {
                "must_fail_on_finding": normalized_finding,
                "reason_code": f"review_failure_derived::{eval_family}",
            },
            "scoring_rubric": {
                "status": "must_fail",
                "requires_traceable_provenance": True,
                "requires_reason_code": f"review_failure_derived::{eval_family}",
            },
            "evaluation_type": "deterministic",
            "created_from": "failure_trace",
            "slice_tags": ["review-eval-024", eval_family, "high-priority" if recurrence_count >= high_priority_threshold else "standard-priority"],
            "provenance": {
                "review_id": review_control_signal.get("review_id"),
                "review_control_signal_id": review_control_signal.get("signal_id"),
                "finding_id": f"finding-{index:03d}",
                "finding_text_normalized": normalized_finding,
                "generated_by_module": "spectrum_systems.modules.runtime.evaluation_auto_generation",
                "dedupe_key": dedupe_key,
                "recurrence_count": recurrence_count,
                "high_priority": recurrence_count >= high_priority_threshold,
            },
        }
        validator.validate(eval_case)
        artifacts.append(eval_case)
    return artifacts


def generate_eval_case_from_failure_pattern(
    *,
    failure_pattern_record: dict[str, Any],
    threshold: int = 3,
    existing_eval_case_ids: Optional[list[str]] = None,
) -> Optional[dict[str, Any]]:
    """Generate deterministic eval_case when a failure pattern recurrence threshold is met."""
    if not isinstance(threshold, int) or threshold <= 0:
        raise EvalCaseGenerationError("threshold must be a positive integer")
    if not isinstance(failure_pattern_record, dict):
        raise EvalCaseGenerationError("failure_pattern_record must be an object")
    _validate_failure_pattern_record(failure_pattern_record)

    occurrence_count = int(failure_pattern_record.get("occurrence_count", 0))
    if occurrence_count < threshold:
        return None

    pattern_id = _string(failure_pattern_record.get("pattern_id"), field="failure_pattern_record.pattern_id")
    normalized_key = _string(
        failure_pattern_record.get("normalized_failure_key"),
        field="failure_pattern_record.normalized_failure_key",
    )
    identity_payload = {
        "pattern_id": pattern_id,
        "normalized_failure_key": normalized_key,
        "threshold": threshold,
    }
    eval_case_id = deterministic_id(
        prefix="ec",
        namespace="batch_l_failure_pattern_eval_case",
        payload=identity_payload,
    )
    if eval_case_id in set(existing_eval_case_ids or []):
        return None

    first_trace = _string(failure_pattern_record.get("trace_ids")[0], field="failure_pattern_record.trace_ids[0]")
    eval_case = {
        "artifact_type": "eval_case",
        "schema_version": "1.0.0",
        "run_id": deterministic_id(prefix="run", namespace="batch_l_failure_pattern_eval_run", payload=identity_payload),
        "trace_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"failure-pattern-eval::{pattern_id}::{threshold}")),
        "eval_case_id": eval_case_id,
        "input_artifact_refs": [f"failure_pattern_record:{pattern_id}"],
        "expected_output_spec": {
            "pass_condition": "future_runs_must_not_repeat_normalized_failure_key",
            "normalized_failure_key": normalized_key,
            "max_allowed_recurrence_count": threshold - 1,
            "anchor_trace_id": first_trace,
        },
        "scoring_rubric": {
            "metric": "failure_pattern_recurrence_count",
            "pass_if_lte": threshold - 1,
            "fail_if_gte": threshold,
            "failure_action": "freeze_or_block",
        },
        "evaluation_type": "deterministic",
        "created_from": "failure_trace",
        "slice_tags": ["batch_l_failure_learning", "recurrence_prevention"],
        "risk_class": "high",
        "priority": "p0",
        "provenance": {
            "source_failure_pattern_record": pattern_id,
            "source_normalized_failure_key": normalized_key,
            "source_failure_pattern_ref": f"failure_pattern_record:{pattern_id}",
            "provenance_refs": [
                f"failure_pattern_record:{pattern_id}",
                f"trace:{first_trace}",
            ],
        },
    }
    Draft202012Validator(load_schema("eval_case"), format_checker=FormatChecker()).validate(eval_case)
    return eval_case


def build_failure_learning_bundle(
    *,
    failure_pattern_record: dict[str, Any],
    remediation_plan: dict[str, Any],
    threshold: int = 3,
    existing_eval_case_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Link failure pattern, remediation, and generated eval into one deterministic enforcement bundle."""
    if not isinstance(remediation_plan, dict):
        raise EvalCaseGenerationError("remediation_plan must be an object")
    pattern_id = _string(failure_pattern_record.get("pattern_id"), field="failure_pattern_record.pattern_id")
    remediation_id = _string(
        remediation_plan.get("plan_id") or remediation_plan.get("remediation_id"),
        field="remediation_plan.plan_id",
    )
    generated_eval_case = generate_eval_case_from_failure_pattern(
        failure_pattern_record=failure_pattern_record,
        threshold=threshold,
        existing_eval_case_ids=existing_eval_case_ids,
    )
    required_eval_set = [generated_eval_case["eval_case_id"]] if generated_eval_case else []
    return {
        "bundle_id": deterministic_id(
            prefix="flb",
            namespace="batch_l_failure_learning_bundle",
            payload={
                "pattern_id": pattern_id,
                "remediation_id": remediation_id,
                "threshold": threshold,
            },
        ),
        "failure_pattern_record_ref": f"failure_pattern_record:{pattern_id}",
        "remediation_plan_ref": f"remediation_plan:{remediation_id}",
        "generated_eval_case": generated_eval_case,
        "required_eval_case_ids": required_eval_set,
        "control_loop_integration": {
            "mode": "required_eval_set_gate",
            "on_violation": "freeze_or_block",
            "threshold": threshold,
        },
    }


def enforce_failure_pattern_eval_gate(
    *,
    failure_pattern_record: dict[str, Any],
    threshold: int = 3,
) -> dict[str, Any]:
    """Deterministic gate decision for future runs based on repeated failure recurrence."""
    _validate_failure_pattern_record(failure_pattern_record)
    if not isinstance(threshold, int) or threshold <= 0:
        raise EvalCaseGenerationError("threshold must be a positive integer")
    recurrence = int(failure_pattern_record.get("occurrence_count", 0))
    violated = recurrence >= threshold
    return {
        "decision": "deny" if violated else "allow",
        "system_response": "freeze" if violated else "allow",
        "reason": (
            "failure_pattern_recurrence_threshold_reached"
            if violated
            else "failure_pattern_recurrence_within_threshold"
        ),
        "required_eval_set_active": violated,
        "recurrence_count": recurrence,
        "threshold": threshold,
    }



def generate_eval_cases_from_cross_run_intelligence(decision: Dict[str, Any]) -> list[Dict[str, Any]]:
    """Generate deterministic eval_case artifacts from cross-run intelligence patterns."""
    if not isinstance(decision, dict):
        raise EvalCaseGenerationError("cross-run decision must be a dict")
    if decision.get("artifact_type") != "cross_run_intelligence_decision":
        raise EvalCaseGenerationError("decision artifact_type must be cross_run_intelligence_decision")
    if "generate_eval_cases" not in list(decision.get("recommended_actions") or []):
        return []

    patterns = list(decision.get("detected_patterns") or [])
    trace_ids = list(decision.get("trace_ids") or [])
    if not trace_ids:
        raise EvalCaseGenerationError("cross-run decision must include trace_ids")

    schema = load_schema("eval_case")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    out: list[Dict[str, Any]] = []
    for pattern in sorted(set(patterns)):
        identity_payload = {
            "intelligence_id": decision.get("intelligence_id"),
            "pattern": pattern,
            "policy_version": decision.get("policy_version"),
            "trace_id": trace_ids[0],
        }
        eval_case = {
            "artifact_type": "eval_case",
            "schema_version": "1.0.0",
            "run_id": deterministic_id(
                prefix="run",
                namespace="xrun_cross_run_eval_case",
                payload={"intelligence_id": decision.get("intelligence_id"), "pattern": pattern},
            ),
            "trace_id": trace_ids[0],
            "eval_case_id": deterministic_id(
                prefix="ec",
                namespace="xrun_cross_run_eval_case",
                payload=identity_payload,
            ),
            "input_artifact_refs": [
                f"cross_run_intelligence_decision:{decision.get('intelligence_id')}",
                f"pattern:{pattern}",
            ],
            "expected_output_spec": {
                "must_detect_pattern": pattern,
                "must_emit_signal_at_or_above": "warning",
            },
            "scoring_rubric": {
                "detection_accuracy": "must_equal_1.0",
                "action_alignment": "must_include_recommended_action",
            },
            "evaluation_type": "deterministic",
            "created_from": "synthetic",
            "slice_tags": ["xrun-01", pattern],
        }
        validator.validate(eval_case)
        out.append(eval_case)
    return out
