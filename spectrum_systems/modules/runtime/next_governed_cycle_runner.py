"""Bounded one-step runner for governed next-cycle execution."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.system_cycle_operator import SystemCycleOperatorError, run_system_cycle


class NextGovernedCycleRunnerError(ValueError):
    """Raised when the bounded next-cycle runner cannot proceed."""


_REQUIRED_BUNDLE_FIELDS = (
    "required_artifacts",
    "active_program_constraints",
    "active_risks",
    "unresolved_blockers",
    "required_reviews",
    "recommended_start_batch",
    "context_refs",
    "continuation_depth",
    "source_cycle_runner_result_ref",
    "autonomy_decision_ref",
    "autonomy_blockers",
    "decision_proof_ref",
    "allow_decision_proof_ref",
    "unknown_state_signal_refs",
    "unknown_state_blockers",
    "latest_exception_class",
    "latest_exception_resolution_action",
    "latest_exception_action_type",
    "latest_exception_requires_human_review",
    "latest_exception_requires_freeze",
    "required_next_actions",
)


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _validate_schema(instance: dict[str, Any], schema_name: str) -> None:
    validator = Draft202012Validator(load_schema(schema_name), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise NextGovernedCycleRunnerError(f"{schema_name} validation failed: {details}")




def _normalize_execution_policy(execution_policy: dict[str, Any] | None) -> dict[str, Any]:
    normalized = dict(execution_policy or {})
    normalized.setdefault("max_batches_per_run", 1)
    normalized.setdefault("max_continuation_depth", 0)
    normalized.setdefault("allow_warn_execution", True)
    normalized.setdefault("stop_on_warn", False)
    normalized.setdefault("stop_on_hard_gate", True)
    _validate_schema(normalized, "execution_policy")
    return normalized
def _build_replay_entry_point(
    *,
    source_cycle_decision_id: str,
    source_cycle_input_bundle_id: str,
    source_cycle_runner_result_ref: str | None,
    executed_cycle_id: str | None,
    next_cycle_decision_ref: str | None,
    next_cycle_input_bundle_ref: str | None,
    emitted_artifact_refs: list[str],
) -> dict[str, Any]:
    execution_refs = [f"roadmap_multi_batch_run_result:{executed_cycle_id}"] if executed_cycle_id else []
    return {
        "input_artifact_refs": sorted(
            set(
                [
                    f"next_cycle_decision:{source_cycle_decision_id}",
                    f"next_cycle_input_bundle:{source_cycle_input_bundle_id}",
                ]
                + ([source_cycle_runner_result_ref] if source_cycle_runner_result_ref else [])
            )
        ),
        "decision_refs": sorted(set([f"next_cycle_decision:{source_cycle_decision_id}"] + ([next_cycle_decision_ref] if next_cycle_decision_ref else []))),
        "bundle_refs": sorted(set([f"next_cycle_input_bundle:{source_cycle_input_bundle_id}"] + ([next_cycle_input_bundle_ref] if next_cycle_input_bundle_ref else []))),
        "execution_refs": sorted(set(execution_refs + list(emitted_artifact_refs))),
    }


def _build_result(
    *,
    source_cycle_decision_id: str,
    source_cycle_input_bundle_id: str,
    source_cycle_runner_result_ref: str | None,
    attempted_execution: bool,
    execution_status: str,
    refusal_reason_codes: list[str],
    refusal_severity: str,
    executed_cycle_id: str | None,
    emitted_artifact_refs: list[str],
    next_cycle_decision_ref: str | None,
    next_cycle_input_bundle_ref: str | None,
    error_detail: dict[str, Any] | str | None,
    created_at: str,
    trace_id: str,
) -> dict[str, Any]:
    id_seed = {
        "source_cycle_decision_id": source_cycle_decision_id,
        "source_cycle_input_bundle_id": source_cycle_input_bundle_id,
        "source_cycle_runner_result_ref": source_cycle_runner_result_ref,
        "attempted_execution": attempted_execution,
        "execution_status": execution_status,
        "refusal_reason_codes": sorted(set(refusal_reason_codes)),
        "executed_cycle_id": executed_cycle_id,
        "next_cycle_decision_ref": next_cycle_decision_ref,
        "next_cycle_input_bundle_ref": next_cycle_input_bundle_ref,
        "trace_id": trace_id,
    }
    result = {
        "cycle_runner_result_id": f"CRR-{_canonical_hash(id_seed)[:12].upper()}",
        "schema_version": "1.0.0",
        "source_cycle_decision_id": source_cycle_decision_id,
        "source_cycle_input_bundle_id": source_cycle_input_bundle_id,
        "attempted_execution": attempted_execution,
        "execution_status": execution_status,
        "refusal_reason_codes": sorted(set(refusal_reason_codes)),
        "refusal_severity": refusal_severity,
        "executed_cycle_id": executed_cycle_id,
        "emitted_artifact_refs": sorted(set(emitted_artifact_refs)),
        "next_cycle_decision_ref": next_cycle_decision_ref,
        "next_cycle_input_bundle_ref": next_cycle_input_bundle_ref,
        "error_detail": error_detail,
        "replay_entry_point": _build_replay_entry_point(
            source_cycle_decision_id=source_cycle_decision_id,
            source_cycle_input_bundle_id=source_cycle_input_bundle_id,
            source_cycle_runner_result_ref=source_cycle_runner_result_ref,
            executed_cycle_id=executed_cycle_id,
            next_cycle_decision_ref=next_cycle_decision_ref,
            next_cycle_input_bundle_ref=next_cycle_input_bundle_ref,
            emitted_artifact_refs=emitted_artifact_refs,
        ),
        "created_at": created_at,
        "trace_id": trace_id,
    }
    _validate_schema(result, "cycle_runner_result")
    return result


def run_next_governed_cycle(
    *,
    next_cycle_decision: dict[str, Any],
    next_cycle_input_bundle: dict[str, Any],
    roadmap_artifact: dict[str, Any],
    selection_signals: dict[str, Any],
    authorization_signals: dict[str, Any],
    integration_inputs: dict[str, Any],
    pqx_state_path: Path,
    pqx_runs_root: Path,
    execution_policy: dict[str, Any] | None = None,
    created_at: str,
    pqx_execute_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute at most one governed next cycle when decision permits, then stop."""

    if not isinstance(created_at, str) or not created_at.strip():
        raise NextGovernedCycleRunnerError("created_at is required for deterministic bounded cycle execution")

    timestamp = created_at
    source_decision_id = str(next_cycle_decision.get("cycle_decision_id", "NCD-000000000000"))
    source_bundle_id = str(next_cycle_input_bundle.get("bundle_id", "NCB-000000000000"))
    trace_id = str(next_cycle_input_bundle.get("trace_id") or next_cycle_decision.get("trace_id") or "trace-next-cycle-runner")

    refusal_reasons: list[str] = []

    try:
        _validate_schema(next_cycle_decision, "next_cycle_decision")
    except NextGovernedCycleRunnerError:
        refusal_reasons.append("decision_invalid")

    try:
        _validate_schema(next_cycle_input_bundle, "next_cycle_input_bundle")
    except NextGovernedCycleRunnerError:
        refusal_reasons.append("input_bundle_invalid")
    missing_fields = [field for field in _REQUIRED_BUNDLE_FIELDS if field not in next_cycle_input_bundle]
    if missing_fields:
        refusal_reasons.append("input_bundle_missing_required_field")

    decision = str(next_cycle_decision.get("decision", ""))
    decision_map = {
        "stop": "decision_stop",
        "escalate": "decision_escalate",
    }
    if decision != "run_next_cycle":
        refusal_reasons.append(decision_map.get(decision, "decision_invalid" if decision else "decision_not_run_next_cycle"))

    if str(next_cycle_decision.get("next_cycle_inputs_ref")) != f"next_cycle_input_bundle:{source_bundle_id}":
        refusal_reasons.append("input_bundle_invalid")

    if str(next_cycle_decision.get("trace_id")) != str(next_cycle_input_bundle.get("trace_id")):
        refusal_reasons.append("trace_mismatch")

    if not isinstance(next_cycle_input_bundle.get("required_artifacts"), list):
        refusal_reasons.append("input_bundle_invalid")

    required_artifacts = [str(item) for item in next_cycle_input_bundle.get("required_artifacts", [])]
    active_program_constraints = [str(item) for item in next_cycle_input_bundle.get("active_program_constraints", [])]
    active_risks = [str(item) for item in next_cycle_input_bundle.get("active_risks", [])]
    unresolved_blockers = [str(item) for item in next_cycle_input_bundle.get("unresolved_blockers", [])]
    required_reviews = [str(item) for item in next_cycle_input_bundle.get("required_reviews", [])]
    autonomy_blockers = [str(item) for item in next_cycle_input_bundle.get("autonomy_blockers", [])]
    unknown_state_blockers = [str(item) for item in next_cycle_input_bundle.get("unknown_state_blockers", [])]
    continuation_depth = int(next_cycle_input_bundle.get("continuation_depth", -1))
    source_cycle_runner_result_ref = (
        str(next_cycle_input_bundle.get("source_cycle_runner_result_ref"))
        if next_cycle_input_bundle.get("source_cycle_runner_result_ref") is not None
        else None
    )
    _recommended_start_batch = next_cycle_input_bundle.get("recommended_start_batch")
    context_refs = [str(item) for item in next_cycle_input_bundle.get("context_refs", [])]
    latest_exception_requires_human_review = bool(next_cycle_input_bundle.get("latest_exception_requires_human_review", False))
    latest_exception_requires_freeze = bool(next_cycle_input_bundle.get("latest_exception_requires_freeze", False))
    required_next_actions = [str(item) for item in next_cycle_input_bundle.get("required_next_actions", [])]

    if not context_refs:
        refusal_reasons.append("input_bundle_invalid")

    if unresolved_blockers:
        refusal_reasons.append("execution_precondition_missing")
    if unknown_state_blockers:
        refusal_reasons.append("execution_precondition_missing")
    if autonomy_blockers:
        refusal_reasons.append("execution_precondition_missing")
    if latest_exception_requires_human_review or latest_exception_requires_freeze:
        refusal_reasons.append("execution_precondition_missing")

    if not required_artifacts:
        refusal_reasons.append("execution_precondition_missing")
    autonomy_decision_ref = str(next_cycle_input_bundle.get("autonomy_decision_ref", ""))
    if not autonomy_decision_ref.startswith("autonomy_decision_record:ADR-"):
        refusal_reasons.append("input_bundle_invalid")
    if not str(next_cycle_input_bundle.get("decision_proof_ref", "")).startswith("decision_proof_record:DPR-"):
        refusal_reasons.append("execution_precondition_missing")
    if not str(next_cycle_input_bundle.get("allow_decision_proof_ref", "")).startswith("allow_decision_proof:ADP-"):
        refusal_reasons.append("execution_precondition_missing")

    normalized_execution_policy: dict[str, Any] | None = None
    try:
        normalized_execution_policy = _normalize_execution_policy(execution_policy)
    except NextGovernedCycleRunnerError:
        refusal_reasons.append("invalid_execution_policy")
    max_continuation_depth = int((normalized_execution_policy or {}).get("max_continuation_depth", 0))

    if continuation_depth < 0:
        refusal_reasons.append("input_bundle_invalid")
    if continuation_depth > max_continuation_depth:
        refusal_reasons.append("continuation_depth_exceeded")

    known_cycle_runner_result_ids = integration_inputs.get("known_cycle_runner_result_ids")
    if not isinstance(known_cycle_runner_result_ids, list) or not source_cycle_runner_result_ref:
        refusal_reasons.append("provenance_chain_invalid")
    elif source_cycle_runner_result_ref.startswith("cycle_runner_result:"):
        source_id = source_cycle_runner_result_ref.split(":", 1)[1]
        if source_id not in {str(item) for item in known_cycle_runner_result_ids}:
            refusal_reasons.append("provenance_chain_invalid")
    else:
        refusal_reasons.append("provenance_chain_invalid")

    if refusal_reasons:
        expected_refusal_only = {"decision_stop", "decision_escalate", "decision_not_run_next_cycle"}
        refusal_severity = "expected" if set(refusal_reasons).issubset(expected_refusal_only) else "abnormal"
        return {
            "cycle_runner_result": _build_result(
                source_cycle_decision_id=source_decision_id,
                source_cycle_input_bundle_id=source_bundle_id,
                source_cycle_runner_result_ref=source_cycle_runner_result_ref,
                attempted_execution=False,
                execution_status="refused",
                refusal_reason_codes=refusal_reasons,
                refusal_severity=refusal_severity,
                executed_cycle_id=None,
                emitted_artifact_refs=sorted(set(required_artifacts + context_refs)),
                next_cycle_decision_ref=None,
                next_cycle_input_bundle_ref=None,
                error_detail=None,
                created_at=timestamp,
                trace_id=trace_id,
            ),
            "executed_cycle": None,
            "bundle_consumption_summary": {
                "required_artifacts": required_artifacts,
                "active_program_constraints": active_program_constraints,
                "active_risks": active_risks,
                "unresolved_blockers": unresolved_blockers,
                "unknown_state_blockers": unknown_state_blockers,
                "required_reviews": required_reviews,
                "continuation_depth": continuation_depth,
                "source_cycle_runner_result_ref": source_cycle_runner_result_ref,
                "recommended_start_batch": _recommended_start_batch,
                "context_refs": context_refs,
                "required_next_actions": required_next_actions,
                "latest_exception_class": str(next_cycle_input_bundle.get("latest_exception_class", "")),
                "latest_exception_resolution_action": str(next_cycle_input_bundle.get("latest_exception_resolution_action", "")),
            },
        }

    try:
        cycle_result = run_system_cycle(
            roadmap_artifact=roadmap_artifact,
            selection_signals=selection_signals,
            authorization_signals=authorization_signals,
            integration_inputs={
                **integration_inputs,
                "continuation_depth": continuation_depth,
                "source_cycle_runner_result_ref": source_cycle_runner_result_ref,
            },
            pqx_state_path=pqx_state_path,
            pqx_runs_root=pqx_runs_root,
            execution_policy=normalized_execution_policy,
            created_at=created_at,
            pqx_execute_fn=pqx_execute_fn,
        )
    except SystemCycleOperatorError as exc:
        return {
            "cycle_runner_result": _build_result(
                source_cycle_decision_id=source_decision_id,
                source_cycle_input_bundle_id=source_bundle_id,
                source_cycle_runner_result_ref=source_cycle_runner_result_ref,
                attempted_execution=True,
                execution_status="failed",
                refusal_reason_codes=["execution_error"],
                refusal_severity="abnormal",
                executed_cycle_id=None,
                emitted_artifact_refs=sorted(set(required_artifacts + context_refs)),
                next_cycle_decision_ref=None,
                next_cycle_input_bundle_ref=None,
                error_detail={"error_type": "SystemCycleOperatorError", "message": str(exc)},
                created_at=timestamp,
                trace_id=trace_id,
            ),
            "executed_cycle": None,
            "bundle_consumption_summary": {
                "required_artifacts": required_artifacts,
                "active_program_constraints": active_program_constraints,
                "active_risks": active_risks,
                "unresolved_blockers": unresolved_blockers,
                "required_reviews": required_reviews,
                "continuation_depth": continuation_depth,
                "source_cycle_runner_result_ref": source_cycle_runner_result_ref,
                "recommended_start_batch": _recommended_start_batch,
                "context_refs": context_refs,
            },
        }

    executed_cycle_id = str(cycle_result["roadmap_multi_batch_run_result"]["run_id"])
    new_decision_ref = f"next_cycle_decision:{cycle_result['next_cycle_decision']['cycle_decision_id']}"
    new_bundle_ref = f"next_cycle_input_bundle:{cycle_result['next_cycle_input_bundle']['bundle_id']}"
    emitted_refs = [
        f"roadmap_multi_batch_run_result:{executed_cycle_id}",
        f"core_system_integration_validation:{cycle_result['core_system_integration_validation']['validation_id']}",
        f"next_step_recommendation:{cycle_result['next_step_recommendation']['recommendation_id']}",
        f"build_summary:{cycle_result['build_summary']['summary_id']}",
        new_decision_ref,
        new_bundle_ref,
    ]
    return {
        "cycle_runner_result": _build_result(
            source_cycle_decision_id=source_decision_id,
            source_cycle_input_bundle_id=source_bundle_id,
            source_cycle_runner_result_ref=source_cycle_runner_result_ref,
            attempted_execution=True,
            execution_status="executed",
            refusal_reason_codes=[],
            refusal_severity="expected",
            executed_cycle_id=executed_cycle_id,
            emitted_artifact_refs=sorted(set(emitted_refs)),
            next_cycle_decision_ref=new_decision_ref,
            next_cycle_input_bundle_ref=new_bundle_ref,
            error_detail=None,
            created_at=timestamp,
            trace_id=trace_id,
        ),
        "executed_cycle": cycle_result,
        "bundle_consumption_summary": {
            "required_artifacts": required_artifacts,
            "active_program_constraints": active_program_constraints,
            "active_risks": active_risks,
            "unresolved_blockers": unresolved_blockers,
            "required_reviews": required_reviews,
            "continuation_depth": continuation_depth,
            "source_cycle_runner_result_ref": source_cycle_runner_result_ref,
            "recommended_start_batch": _recommended_start_batch,
            "context_refs": context_refs,
            "required_next_actions": required_next_actions,
            "latest_exception_class": str(next_cycle_input_bundle.get("latest_exception_class", "")),
            "latest_exception_resolution_action": str(next_cycle_input_bundle.get("latest_exception_resolution_action", "")),
        },
    }


__all__ = ["NextGovernedCycleRunnerError", "run_next_governed_cycle"]
