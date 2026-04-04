"""Bounded one-step runner for governed next-cycle execution."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
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
    "recommended_start_batch",
    "context_refs",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _validate_schema(instance: dict[str, Any], schema_name: str) -> None:
    validator = Draft202012Validator(load_schema(schema_name), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise NextGovernedCycleRunnerError(f"{schema_name} validation failed: {details}")


def _build_result(
    *,
    source_cycle_decision_id: str,
    source_cycle_input_bundle_id: str,
    attempted_execution: bool,
    execution_status: str,
    refusal_reason_codes: list[str],
    executed_cycle_id: str | None,
    emitted_artifact_refs: list[str],
    next_cycle_decision_ref: str | None,
    next_cycle_input_bundle_ref: str | None,
    created_at: str,
    trace_id: str,
) -> dict[str, Any]:
    id_seed = {
        "source_cycle_decision_id": source_cycle_decision_id,
        "source_cycle_input_bundle_id": source_cycle_input_bundle_id,
        "attempted_execution": attempted_execution,
        "execution_status": execution_status,
        "refusal_reason_codes": sorted(set(refusal_reason_codes)),
        "executed_cycle_id": executed_cycle_id,
        "next_cycle_decision_ref": next_cycle_decision_ref,
        "next_cycle_input_bundle_ref": next_cycle_input_bundle_ref,
        "trace_id": trace_id,
        "created_at": created_at,
    }
    result = {
        "cycle_runner_result_id": f"CRR-{_canonical_hash(id_seed)[:12].upper()}",
        "schema_version": "1.0.0",
        "source_cycle_decision_id": source_cycle_decision_id,
        "source_cycle_input_bundle_id": source_cycle_input_bundle_id,
        "attempted_execution": attempted_execution,
        "execution_status": execution_status,
        "refusal_reason_codes": sorted(set(refusal_reason_codes)),
        "executed_cycle_id": executed_cycle_id,
        "emitted_artifact_refs": sorted(set(emitted_artifact_refs)),
        "next_cycle_decision_ref": next_cycle_decision_ref,
        "next_cycle_input_bundle_ref": next_cycle_input_bundle_ref,
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
    created_at: str | None = None,
    pqx_execute_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute at most one governed next cycle when decision permits, then stop."""

    timestamp = created_at or _utc_now()
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

    # Consume required input bundle surface explicitly for governed handoff checks.
    required_artifacts = [str(item) for item in next_cycle_input_bundle.get("required_artifacts", [])]
    active_program_constraints = [str(item) for item in next_cycle_input_bundle.get("active_program_constraints", [])]
    active_risks = [str(item) for item in next_cycle_input_bundle.get("active_risks", [])]
    unresolved_blockers = [str(item) for item in next_cycle_input_bundle.get("unresolved_blockers", [])]
    _recommended_start_batch = next_cycle_input_bundle.get("recommended_start_batch")
    context_refs = [str(item) for item in next_cycle_input_bundle.get("context_refs", [])]

    if not context_refs:
        refusal_reasons.append("input_bundle_invalid")

    if unresolved_blockers:
        refusal_reasons.append("execution_precondition_missing")

    if not required_artifacts:
        refusal_reasons.append("execution_precondition_missing")

    if refusal_reasons:
        return {
            "cycle_runner_result": _build_result(
                source_cycle_decision_id=source_decision_id,
                source_cycle_input_bundle_id=source_bundle_id,
                attempted_execution=False,
                execution_status="refused",
                refusal_reason_codes=refusal_reasons,
                executed_cycle_id=None,
                emitted_artifact_refs=sorted(set(required_artifacts + context_refs)),
                next_cycle_decision_ref=None,
                next_cycle_input_bundle_ref=None,
                created_at=timestamp,
                trace_id=trace_id,
            ),
            "executed_cycle": None,
            "bundle_consumption_summary": {
                "required_artifacts": required_artifacts,
                "active_program_constraints": active_program_constraints,
                "active_risks": active_risks,
                "unresolved_blockers": unresolved_blockers,
                "recommended_start_batch": _recommended_start_batch,
                "context_refs": context_refs,
            },
        }

    try:
        cycle_result = run_system_cycle(
            roadmap_artifact=roadmap_artifact,
            selection_signals=selection_signals,
            authorization_signals=authorization_signals,
            integration_inputs=integration_inputs,
            pqx_state_path=pqx_state_path,
            pqx_runs_root=pqx_runs_root,
            execution_policy=execution_policy,
            created_at=created_at,
            pqx_execute_fn=pqx_execute_fn,
        )
    except (SystemCycleOperatorError, ValueError, TypeError) as exc:
        return {
            "cycle_runner_result": _build_result(
                source_cycle_decision_id=source_decision_id,
                source_cycle_input_bundle_id=source_bundle_id,
                attempted_execution=True,
                execution_status="failed",
                refusal_reason_codes=["execution_error"],
                executed_cycle_id=None,
                emitted_artifact_refs=sorted(set(required_artifacts + context_refs + [f"error:{exc}"])),
                next_cycle_decision_ref=None,
                next_cycle_input_bundle_ref=None,
                created_at=timestamp,
                trace_id=trace_id,
            ),
            "executed_cycle": None,
            "bundle_consumption_summary": {
                "required_artifacts": required_artifacts,
                "active_program_constraints": active_program_constraints,
                "active_risks": active_risks,
                "unresolved_blockers": unresolved_blockers,
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
            attempted_execution=True,
            execution_status="executed",
            refusal_reason_codes=[],
            executed_cycle_id=executed_cycle_id,
            emitted_artifact_refs=sorted(set(emitted_refs)),
            next_cycle_decision_ref=new_decision_ref,
            next_cycle_input_bundle_ref=new_bundle_ref,
            created_at=timestamp,
            trace_id=trace_id,
        ),
        "executed_cycle": cycle_result,
        "bundle_consumption_summary": {
            "required_artifacts": required_artifacts,
            "active_program_constraints": active_program_constraints,
            "active_risks": active_risks,
            "unresolved_blockers": unresolved_blockers,
            "recommended_start_batch": _recommended_start_batch,
            "context_refs": context_refs,
        },
    }


__all__ = ["NextGovernedCycleRunnerError", "run_next_governed_cycle"]
