"""Deterministic bounded multi-batch roadmap execution (RDX-006)."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.roadmap_execution_loop_validator import (
    RoadmapExecutionLoopValidationError,
    validate_single_batch_execution_loop,
)


class RoadmapMultiBatchExecutionError(ValueError):
    """Raised when bounded multi-batch roadmap execution cannot be computed safely."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _canonical_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _run_id(seed: dict[str, Any]) -> str:
    return f"RMB-{_canonical_hash(seed)[:12].upper()}"


def _validate_schema(instance: dict[str, Any], schema_name: str, *, label: str) -> None:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise RoadmapMultiBatchExecutionError(f"{label} failed schema validation ({schema_name}): {details}")


def _normalize_policy(execution_policy: dict[str, Any] | None) -> dict[str, Any]:
    raw = dict(execution_policy or {})
    max_batches = raw.get("max_batches_per_run", 2)
    if not isinstance(max_batches, int) or max_batches < 1:
        raise RoadmapMultiBatchExecutionError("execution_policy.max_batches_per_run must be an integer >= 1")

    allow_warn_execution = bool(raw.get("allow_warn_execution", True))
    stop_on_warn = bool(raw.get("stop_on_warn", False))
    stop_on_hard_gate = bool(raw.get("stop_on_hard_gate", True))

    return {
        "max_batches_per_run": max_batches,
        "allow_warn_execution": allow_warn_execution,
        "stop_on_warn": stop_on_warn,
        "stop_on_hard_gate": stop_on_hard_gate,
    }


def _resolve_batch(roadmap_artifact: dict[str, Any], batch_id: str) -> dict[str, Any] | None:
    for batch in roadmap_artifact.get("batches", []):
        if isinstance(batch, dict) and batch.get("batch_id") == batch_id:
            return batch
    return None


def execute_bounded_roadmap_run(
    roadmap_artifact: dict[str, Any],
    selection_signals: dict[str, Any],
    authorization_signals: dict[str, Any],
    *,
    pqx_state_path: Path,
    pqx_runs_root: Path,
    execution_policy: dict[str, Any] | None = None,
    evaluated_at: str | None = None,
    executed_at: str | None = None,
    validated_at: str | None = None,
    run_executed_at: str | None = None,
    source_refs: list[str] | None = None,
    pqx_execute_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute up to ``max_batches_per_run`` roadmap batches with strict fail-closed stop conditions."""
    _validate_schema(roadmap_artifact, "roadmap_artifact", label="roadmap_artifact")
    policy = _normalize_policy(execution_policy)

    if not isinstance(selection_signals, dict):
        raise RoadmapMultiBatchExecutionError("selection_signals must be an object")
    if not isinstance(authorization_signals, dict):
        raise RoadmapMultiBatchExecutionError("authorization_signals must be an object")

    trace_id = str(authorization_signals.get("trace_id") or "").strip() or "trace-missing"
    timestamp = run_executed_at or validated_at or executed_at or evaluated_at or _utc_now()

    input_payload = {
        "roadmap_artifact": roadmap_artifact,
        "selection_signals": selection_signals,
        "authorization_signals": authorization_signals,
        "execution_policy": policy,
        "pqx_state_path": str(pqx_state_path),
        "pqx_runs_root": str(pqx_runs_root),
        "evaluated_at": evaluated_at,
        "executed_at": executed_at,
        "validated_at": validated_at,
    }
    input_hash = _canonical_hash(input_payload)

    normalized_source_refs = sorted(
        set((source_refs or []) + ["roadmap_artifact:inline", "roadmap_execution_loop_validation:inline"])
    )

    attempted_batch_ids: list[str] = []
    completed_batch_ids: list[str] = []
    authorization_refs: list[str] = []
    progress_update_refs: list[str] = []
    loop_validation_refs: list[str] = []

    blocked_batch_id: str | None = None
    frozen_batch_id: str | None = None
    stop_reason = "MAX_BATCHES_REACHED"
    stop_reason_codes: list[str] = ["MAX_BATCHES_REACHED"]

    current_roadmap = copy.deepcopy(roadmap_artifact)

    for _ in range(policy["max_batches_per_run"]):
        try:
            loop_result = validate_single_batch_execution_loop(
                current_roadmap,
                selection_signals,
                authorization_signals,
                pqx_state_path=pqx_state_path,
                pqx_runs_root=pqx_runs_root,
                evaluated_at=evaluated_at,
                executed_at=executed_at,
                validated_at=validated_at,
                pqx_execute_fn=pqx_execute_fn,
            )
        except RoadmapExecutionLoopValidationError as exc:
            stop_reason = "CONTRACT_PRECONDITION_FAILURE"
            stop_reason_codes = ["CONTRACT_PRECONDITION_FAILURE", str(exc)]
            break

        selection = loop_result["selection_result"]
        authorization = loop_result["authorization_result"]
        progress = loop_result["progress_update"]
        loop_validation = loop_result["loop_validation"]
        updated_roadmap = loop_result["roadmap"]

        selected_batch_id = selection.get("selected_batch_id")
        if isinstance(selected_batch_id, str):
            attempted_batch_ids.append(selected_batch_id)

        authorization_refs.append(str(authorization.get("authorization_id")))
        loop_validation_refs.append(str(loop_validation.get("validation_id")))
        if isinstance(progress, dict) and isinstance(progress.get("progress_update_id"), str):
            progress_update_refs.append(progress["progress_update_id"])

        control_decision = authorization.get("control_decision")
        if control_decision == "freeze":
            frozen_batch_id = selected_batch_id if isinstance(selected_batch_id, str) else None
            stop_reason = "CONTROL_FREEZE"
            stop_reason_codes = ["CONTROL_FREEZE"]
            break
        if control_decision == "block":
            blocked_batch_id = selected_batch_id if isinstance(selected_batch_id, str) else None
            stop_reason = "CONTROL_BLOCK"
            stop_reason_codes = ["CONTROL_BLOCK"]
            break
        if control_decision == "warn" and not policy["allow_warn_execution"]:
            stop_reason = "AUTHORIZATION_INVALID"
            stop_reason_codes = ["WARN_DISALLOWED_BY_POLICY"]
            break
        if control_decision == "warn" and policy["stop_on_warn"]:
            stop_reason = "AUTHORIZATION_WARN_STOP"
            stop_reason_codes = ["STOP_ON_WARN_POLICY"]
            break

        if loop_validation.get("loop_status") != "passed":
            stop_reason = "LOOP_VALIDATION_FAILURE"
            stop_reason_codes = sorted(set(["LOOP_VALIDATION_FAILURE"] + list(loop_validation.get("reason_codes", []))))
            break
        if loop_validation.get("replay_ready") is not True:
            stop_reason = "REPLAY_NOT_READY"
            stop_reason_codes = ["REPLAY_NOT_READY"]
            break

        if not isinstance(progress, dict):
            stop_reason = "INVALID_PROGRESS_STATE"
            stop_reason_codes = ["MISSING_PROGRESS_UPDATE"]
            break

        execution_status = progress.get("execution_status")
        if execution_status == "succeeded":
            if not isinstance(selected_batch_id, str):
                stop_reason = "INVALID_ROADMAP_STATE"
                stop_reason_codes = ["MISSING_SELECTED_BATCH_ID"]
                break
            completed_batch_ids.append(selected_batch_id)
        elif execution_status == "blocked":
            blocked_batch_id = selected_batch_id if isinstance(selected_batch_id, str) else None
            stop_reason = "PQX_EXECUTION_BLOCKED"
            stop_reason_codes = ["PQX_EXECUTION_BLOCKED"]
            break
        elif execution_status in {"failed", "not_executed"}:
            stop_reason = "PQX_EXECUTION_FAILURE"
            stop_reason_codes = ["PQX_EXECUTION_FAILURE"]
            break
        else:
            stop_reason = "INVALID_PROGRESS_STATE"
            stop_reason_codes = ["UNKNOWN_EXECUTION_STATUS"]
            break

        if isinstance(selected_batch_id, str):
            selected_batch = _resolve_batch(updated_roadmap, selected_batch_id)
            if selected_batch is None:
                stop_reason = "INVALID_ROADMAP_STATE"
                stop_reason_codes = ["SELECTED_BATCH_NOT_FOUND_AFTER_UPDATE"]
                break
            if policy["stop_on_hard_gate"] and bool(selected_batch.get("hard_gate_after", False)):
                stop_reason = "HARD_GATE_STOP"
                stop_reason_codes = ["HARD_GATE_AFTER_COMPLETED_BATCH"]
                current_roadmap = updated_roadmap
                break

        current_roadmap = updated_roadmap
    else:
        stop_reason = "MAX_BATCHES_REACHED"
        stop_reason_codes = ["MAX_BATCHES_REACHED"]

    seed = {
        "roadmap_id": roadmap_artifact["roadmap_id"],
        "attempted_batch_ids": attempted_batch_ids,
        "completed_batch_ids": completed_batch_ids,
        "stop_reason": stop_reason,
        "max_batches_per_run": policy["max_batches_per_run"],
        "input_hash": input_hash,
        "executed_at": timestamp,
    }

    result = {
        "run_id": _run_id(seed),
        "schema_version": "1.0.0",
        "roadmap_id": roadmap_artifact["roadmap_id"],
        "attempted_batch_ids": attempted_batch_ids,
        "completed_batch_ids": completed_batch_ids,
        "blocked_batch_id": blocked_batch_id,
        "frozen_batch_id": frozen_batch_id,
        "stop_reason": stop_reason,
        "stop_reason_codes": stop_reason_codes,
        "max_batches_per_run": policy["max_batches_per_run"],
        "batches_executed_count": len(completed_batch_ids),
        "final_roadmap_status_ref": f"roadmap_artifact:inline:{current_roadmap['roadmap_id']}",
        "loop_validation_refs": loop_validation_refs,
        "progress_update_refs": progress_update_refs,
        "authorization_refs": authorization_refs,
        "executed_at": timestamp,
        "input_hash": input_hash,
        "trace_id": trace_id,
        "source_refs": normalized_source_refs,
    }
    _validate_schema(result, "roadmap_multi_batch_run_result", label="roadmap_multi_batch_run_result")
    return {
        "roadmap": current_roadmap,
        "run_result": result,
    }


__all__ = [
    "RoadmapMultiBatchExecutionError",
    "execute_bounded_roadmap_run",
]
