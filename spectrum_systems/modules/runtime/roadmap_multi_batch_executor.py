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
from spectrum_systems.modules.runtime.roadmap_stop_reasons import (
    STOP_REASON_AUTHORIZATION_BLOCK,
    STOP_REASON_AUTHORIZATION_FREEZE,
    STOP_REASON_CONTRACT_PRECONDITION_FAILED,
    STOP_REASON_EXECUTION_BLOCKED,
    STOP_REASON_EXECUTION_FAILED,
    STOP_REASON_HARD_GATE_STOP,
    STOP_REASON_INVALID_PROGRESS_STATE,
    STOP_REASON_INVALID_ROADMAP_STATE,
    STOP_REASON_LOOP_VALIDATION_FAILED,
    STOP_REASON_MAX_BATCHES_REACHED,
    STOP_REASON_NO_ELIGIBLE_BATCH,
    STOP_REASON_REPLAY_NOT_READY,
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
    stop_reason = STOP_REASON_MAX_BATCHES_REACHED
    stop_reason_codes: list[str] = [STOP_REASON_MAX_BATCHES_REACHED]

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
            stop_reason = STOP_REASON_CONTRACT_PRECONDITION_FAILED
            stop_reason_codes = [STOP_REASON_CONTRACT_PRECONDITION_FAILED]
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
            stop_reason = STOP_REASON_AUTHORIZATION_FREEZE
            stop_reason_codes = [STOP_REASON_AUTHORIZATION_FREEZE]
            break
        if control_decision == "block":
            blocked_batch_id = selected_batch_id if isinstance(selected_batch_id, str) else None
            stop_reason = str(authorization.get("stop_reason") or STOP_REASON_AUTHORIZATION_BLOCK)
            stop_reason_codes = [stop_reason]
            break
        if control_decision == "warn" and not policy["allow_warn_execution"]:
            stop_reason = STOP_REASON_AUTHORIZATION_BLOCK
            stop_reason_codes = [STOP_REASON_AUTHORIZATION_BLOCK]
            break
        if control_decision == "warn" and policy["stop_on_warn"]:
            stop_reason = STOP_REASON_AUTHORIZATION_BLOCK
            stop_reason_codes = [STOP_REASON_AUTHORIZATION_BLOCK]
            break

        if loop_validation.get("loop_status") != "passed":
            stop_reason = str(loop_validation.get("stop_reason") or STOP_REASON_LOOP_VALIDATION_FAILED)
            stop_reason_codes = [stop_reason]
            break
        if loop_validation.get("replay_ready") is not True:
            stop_reason = STOP_REASON_REPLAY_NOT_READY
            stop_reason_codes = [STOP_REASON_REPLAY_NOT_READY]
            break

        if not isinstance(progress, dict):
            stop_reason = STOP_REASON_INVALID_PROGRESS_STATE
            stop_reason_codes = [STOP_REASON_INVALID_PROGRESS_STATE]
            break

        execution_status = progress.get("execution_status")
        if execution_status == "succeeded":
            if not isinstance(selected_batch_id, str):
                stop_reason = STOP_REASON_INVALID_ROADMAP_STATE
                stop_reason_codes = [STOP_REASON_INVALID_ROADMAP_STATE]
                break
            completed_batch_ids.append(selected_batch_id)
        elif execution_status == "blocked":
            blocked_batch_id = selected_batch_id if isinstance(selected_batch_id, str) else None
            stop_reason = str(progress.get("stop_reason") or STOP_REASON_EXECUTION_BLOCKED)
            stop_reason_codes = [stop_reason]
            break
        elif execution_status in {"failed", "not_executed"}:
            if execution_status == "not_executed":
                stop_reason = str(progress.get("stop_reason") or STOP_REASON_AUTHORIZATION_BLOCK)
            else:
                stop_reason = str(progress.get("stop_reason") or STOP_REASON_EXECUTION_FAILED)
            stop_reason_codes = [stop_reason]
            break
        else:
            stop_reason = STOP_REASON_INVALID_PROGRESS_STATE
            stop_reason_codes = [STOP_REASON_INVALID_PROGRESS_STATE]
            break

        if isinstance(selected_batch_id, str):
            selected_batch = _resolve_batch(updated_roadmap, selected_batch_id)
            if selected_batch is None:
                stop_reason = STOP_REASON_INVALID_ROADMAP_STATE
                stop_reason_codes = [STOP_REASON_INVALID_ROADMAP_STATE]
                break
            if policy["stop_on_hard_gate"] and bool(selected_batch.get("hard_gate_after", False)):
                stop_reason = STOP_REASON_HARD_GATE_STOP
                stop_reason_codes = [STOP_REASON_HARD_GATE_STOP]
                current_roadmap = updated_roadmap
                break
        elif selection.get("stop_reason") == STOP_REASON_NO_ELIGIBLE_BATCH:
            stop_reason = STOP_REASON_NO_ELIGIBLE_BATCH
            stop_reason_codes = [STOP_REASON_NO_ELIGIBLE_BATCH]
            break

        current_roadmap = updated_roadmap
    else:
        stop_reason = STOP_REASON_MAX_BATCHES_REACHED
        stop_reason_codes = [STOP_REASON_MAX_BATCHES_REACHED]

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
        "schema_version": "1.1.0",
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
