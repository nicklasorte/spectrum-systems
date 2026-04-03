"""Deterministic authorized roadmap batch execution and progress update (RDX-004)."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.pqx_sequence_runner import execute_sequence_run
from spectrum_systems.modules.runtime.roadmap_stop_reasons import (
    STOP_REASON_AUTHORIZATION_BLOCK,
    STOP_REASON_AUTHORIZATION_FREEZE,
    STOP_REASON_EXECUTION_BLOCKED,
    STOP_REASON_EXECUTION_FAILED,
)


class RoadmapExecutorError(ValueError):
    """Raised when authorized roadmap execution cannot proceed safely."""


_ALLOWED_BATCH_EXECUTION_DECISIONS = {"allow", "warn"}
_ALLOWED_BATCH_STATUSES = {"not_started", "running", "completed", "blocked"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _canonical_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _progress_update_id(seed: dict[str, Any]) -> str:
    return f"RPU-{_canonical_hash(seed)[:12].upper()}"


def _validate_schema(instance: dict[str, Any], schema_name: str, *, label: str) -> None:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise RoadmapExecutorError(f"{label} failed schema validation ({schema_name}): {details}")


def _resolve_batch(roadmap_artifact: dict[str, Any], batch_id: str) -> tuple[int, dict[str, Any]]:
    for index, batch in enumerate(roadmap_artifact.get("batches", [])):
        if isinstance(batch, dict) and batch.get("batch_id") == batch_id:
            return index, batch
    raise RoadmapExecutorError(f"selected batch not present in roadmap_artifact.batches: {batch_id}")


def _derive_next_candidate_batch_id(roadmap_artifact: dict[str, Any]) -> str | None:
    batches = roadmap_artifact.get("batches", [])
    status_by_id = {
        row.get("batch_id"): row.get("status")
        for row in batches
        if isinstance(row, dict) and isinstance(row.get("batch_id"), str)
    }
    for batch in batches:
        if not isinstance(batch, dict) or batch.get("status") != "not_started":
            continue
        dependencies = batch.get("depends_on", [])
        if not isinstance(dependencies, list):
            continue
        if all(status_by_id.get(dep) == "completed" for dep in dependencies):
            batch_id = batch.get("batch_id")
            if isinstance(batch_id, str):
                return batch_id
    return None


def _derive_next_hard_gate(roadmap_artifact: dict[str, Any]) -> str:
    for batch in roadmap_artifact.get("batches", []):
        if not isinstance(batch, dict):
            continue
        if batch.get("hard_gate_after") is True and batch.get("status") != "completed":
            batch_id = batch.get("batch_id")
            if isinstance(batch_id, str):
                return f"HARD_GATE_AFTER_{batch_id}"
    previous = roadmap_artifact.get("next_hard_gate")
    if isinstance(previous, str) and previous:
        return previous
    return "NONE"


def _build_slice_requests(step_ids: list[str], trace_id: str) -> list[dict[str, str]]:
    requests: list[dict[str, str]] = []
    seen: set[str] = set()
    for step_id in step_ids:
        if not isinstance(step_id, str) or not step_id:
            raise RoadmapExecutorError("selected batch step_ids must contain non-empty strings")
        if step_id in seen:
            raise RoadmapExecutorError(f"duplicate step_id in selected batch: {step_id}")
        seen.add(step_id)
        requests.append({"slice_id": step_id, "trace_id": trace_id})
    if not requests:
        raise RoadmapExecutorError("selected batch step_ids must be non-empty")
    return requests


def _collect_pqx_refs(pqx_result: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for row in pqx_result.get("execution_history", []):
        if not isinstance(row, dict):
            continue
        for field in ("execution_ref", "slice_execution_record_ref", "certification_ref", "audit_bundle_ref"):
            value = row.get(field)
            if isinstance(value, str) and value:
                refs.append(value)
    return sorted(set(refs))


def _map_pqx_status_to_execution_status(pqx_result: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    status = pqx_result.get("status")
    if status == "completed":
        return "succeeded", ["PQX_EXECUTION_SUCCEEDED"], []
    if status == "blocked":
        reason = str(pqx_result.get("blocked_reason") or "pqx reported blocked status")
        return "blocked", ["PQX_EXECUTION_BLOCKED"], [reason]
    reason = str(pqx_result.get("blocked_reason") or f"pqx returned non-completed status: {status}")
    return "failed", ["PQX_EXECUTION_FAILED"], [reason]


def update_roadmap_after_execution(
    roadmap_artifact: dict[str, Any],
    *,
    selected_batch_id: str,
    execution_status: str,
) -> dict[str, Any]:
    """Apply deterministic one-batch status progression after execution outcome is known."""
    updated = copy.deepcopy(roadmap_artifact)
    index, batch = _resolve_batch(updated, selected_batch_id)
    previous_status = batch.get("status")
    if previous_status not in _ALLOWED_BATCH_STATUSES:
        raise RoadmapExecutorError(f"selected batch has unsupported status: {previous_status}")
    if previous_status in {"completed", "blocked"}:
        raise RoadmapExecutorError("selected batch must not be terminal before execution")

    if execution_status == "succeeded":
        new_status = "completed"
    elif execution_status in {"blocked", "failed", "not_executed"}:
        new_status = "blocked" if execution_status != "not_executed" else previous_status
    else:
        raise RoadmapExecutorError(f"unsupported execution_status: {execution_status}")

    if previous_status == "not_started" and new_status not in {"not_started", "completed", "blocked"}:
        raise RoadmapExecutorError("illegal status transition for selected batch")
    if previous_status == "running" and new_status not in {"completed", "blocked"}:
        raise RoadmapExecutorError("illegal status transition for selected batch")

    updated_batch = dict(batch)
    updated_batch["status"] = new_status
    updated["batches"][index] = updated_batch

    next_candidate = _derive_next_candidate_batch_id(updated)
    updated["current_batch_id"] = next_candidate or selected_batch_id
    updated["next_hard_gate"] = _derive_next_hard_gate(updated)
    return updated


def execute_authorized_batch(
    roadmap_artifact: dict[str, Any],
    roadmap_selection_result: dict[str, Any],
    roadmap_execution_authorization: dict[str, Any],
    *,
    pqx_state_path: Path,
    pqx_runs_root: Path,
    executed_at: str | None = None,
    pqx_execute_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute one selected roadmap batch through PQX only when authorization permits it."""
    _validate_schema(roadmap_artifact, "roadmap_artifact", label="roadmap_artifact")
    _validate_schema(roadmap_selection_result, "roadmap_selection_result", label="roadmap_selection_result")
    _validate_schema(
        roadmap_execution_authorization,
        "roadmap_execution_authorization",
        label="roadmap_execution_authorization",
    )

    selected_batch_id = roadmap_selection_result.get("selected_batch_id")
    authorization_batch_id = roadmap_execution_authorization.get("selected_batch_id")
    if not isinstance(selected_batch_id, str) or not selected_batch_id:
        raise RoadmapExecutorError("roadmap_selection_result.selected_batch_id must be a non-empty string")
    if selected_batch_id != authorization_batch_id:
        raise RoadmapExecutorError("authorization selected_batch_id must match roadmap_selection_result.selected_batch_id")
    if roadmap_selection_result.get("ready_to_run") is not True:
        raise RoadmapExecutorError("roadmap_selection_result.ready_to_run must be true before execution")

    _, selected_batch = _resolve_batch(roadmap_artifact, selected_batch_id)

    control_decision = roadmap_execution_authorization.get("control_decision")
    authorized_to_run = roadmap_execution_authorization.get("authorized_to_run")
    if control_decision in _ALLOWED_BATCH_EXECUTION_DECISIONS and authorized_to_run is True:
        execution_allowed = True
    elif control_decision in {"freeze", "block"} and authorized_to_run is False:
        execution_allowed = False
    else:
        raise RoadmapExecutorError("authorization control_decision/authorized_to_run combination is inconsistent")

    input_hash = _canonical_hash(
        {
            "roadmap_artifact": roadmap_artifact,
            "roadmap_selection_result": roadmap_selection_result,
            "roadmap_execution_authorization": roadmap_execution_authorization,
        }
    )

    trace_id = roadmap_execution_authorization["trace_id"]
    timestamp = executed_at or _utc_now()
    pqx_refs: list[str] = []
    reason_codes: list[str]
    blocking_conditions: list[str]
    execution_status: str
    pqx_result_summary: dict[str, Any]
    stop_reason: str | None = None

    if not execution_allowed:
        execution_status = "not_executed"
        reason_codes = ["AUTHORIZATION_DENIED_EXECUTION"]
        blocking_conditions = sorted(set(str(row) for row in roadmap_execution_authorization.get("blocking_conditions", [])))
        if control_decision == "freeze":
            stop_reason = STOP_REASON_AUTHORIZATION_FREEZE
        else:
            stop_reason = STOP_REASON_AUTHORIZATION_BLOCK
        pqx_result_summary = {
            "status": "not_executed",
            "control_decision": control_decision,
            "authorized_to_run": False,
            "authorization_id": roadmap_execution_authorization.get("authorization_id"),
        }
        updated_roadmap = copy.deepcopy(roadmap_artifact)
    else:
        step_ids = selected_batch.get("step_ids")
        if not isinstance(step_ids, list):
            raise RoadmapExecutorError("selected batch step_ids must be a list")
        slice_requests = _build_slice_requests(step_ids, trace_id)

        queue_run_id = f"queue-{selected_batch_id.lower()}"
        run_id = f"run-{selected_batch_id.lower()}"

        execute_fn = pqx_execute_fn or execute_sequence_run
        state_path = Path(pqx_state_path)
        runs_root = Path(pqx_runs_root)
        if state_path.parent != runs_root:
            raise RoadmapExecutorError("pqx_state_path must be located directly under pqx_runs_root for deterministic linkage")

        pqx_result = execute_fn(
            slice_requests=slice_requests,
            state_path=state_path,
            queue_run_id=queue_run_id,
            run_id=run_id,
            trace_id=trace_id,
            max_slices=len(slice_requests),
        )
        if not isinstance(pqx_result, dict):
            raise RoadmapExecutorError("PQX execution seam must return an object")

        execution_status, reason_codes, blocking_conditions = _map_pqx_status_to_execution_status(pqx_result)
        if execution_status == "blocked":
            stop_reason = STOP_REASON_EXECUTION_BLOCKED
        elif execution_status == "failed":
            stop_reason = STOP_REASON_EXECUTION_FAILED
        pqx_refs = _collect_pqx_refs(pqx_result)
        pqx_result_summary = {
            "status": pqx_result.get("status"),
            "batch_result": pqx_result.get("batch_result"),
            "blocked_reason": pqx_result.get("blocked_reason"),
            "execution_history": pqx_result.get("execution_history"),
        }
        updated_roadmap = update_roadmap_after_execution(
            roadmap_artifact,
            selected_batch_id=selected_batch_id,
            execution_status=execution_status,
        )

    _, updated_batch = _resolve_batch(updated_roadmap, selected_batch_id)
    previous_status = selected_batch.get("status")
    new_status = updated_batch.get("status")

    next_candidate_batch_id = _derive_next_candidate_batch_id(updated_roadmap)
    execution_result_hash = _canonical_hash({"execution_status": execution_status, "pqx_result": pqx_result_summary})

    source_refs = sorted(
        set(
            [
                "roadmap_artifact:inline",
                "roadmap_selection_result:inline",
                "roadmap_execution_authorization:inline",
            ]
            + [str(item) for item in roadmap_execution_authorization.get("source_refs", []) if isinstance(item, str) and item]
        )
    )

    progress_seed = {
        "roadmap_id": roadmap_artifact["roadmap_id"],
        "batch_id": selected_batch_id,
        "authorization_id": roadmap_execution_authorization["authorization_id"],
        "execution_status": execution_status,
        "executed_at": timestamp,
        "roadmap_input_hash": input_hash,
        "execution_result_hash": execution_result_hash,
    }
    progress_update = {
        "progress_update_id": _progress_update_id(progress_seed),
        "schema_version": "1.1.0",
        "roadmap_id": roadmap_artifact["roadmap_id"],
        "batch_id": selected_batch_id,
        "previous_batch_status": previous_status,
        "new_batch_status": new_status,
        "execution_status": execution_status,
        "pqx_execution_refs": pqx_refs,
        "selected_batch_id": selected_batch_id,
        "authorization_id": roadmap_execution_authorization["authorization_id"],
        "executed_at": timestamp,
        "reason_codes": sorted(set(reason_codes)),
        "stop_reason": stop_reason,
        "stop_reason_codes": [stop_reason] if isinstance(stop_reason, str) else [],
        "blocking_conditions": sorted(set(blocking_conditions)),
        "next_candidate_batch_id": next_candidate_batch_id,
        "roadmap_input_hash": input_hash,
        "execution_result_hash": execution_result_hash,
        "trace_id": trace_id,
        "source_refs": source_refs,
    }
    validate_roadmap_progress_update(progress_update)

    return {
        "roadmap": updated_roadmap,
        "progress_update": progress_update,
        "pqx_called": execution_allowed,
        "pqx_result": pqx_result_summary,
    }


def validate_roadmap_progress_update(payload: dict[str, Any]) -> None:
    _validate_schema(payload, "roadmap_progress_update", label="roadmap_progress_update")


def write_roadmap_progress_update(payload: dict[str, Any], output_path: Path) -> Path:
    validate_roadmap_progress_update(payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def read_roadmap_progress_update(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RoadmapExecutorError(f"roadmap_progress_update artifact not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RoadmapExecutorError(f"roadmap_progress_update artifact is not valid JSON: {path}") from exc

    if not isinstance(loaded, dict):
        raise RoadmapExecutorError("roadmap_progress_update artifact root must be a JSON object")
    validate_roadmap_progress_update(loaded)
    return loaded


__all__ = [
    "RoadmapExecutorError",
    "execute_authorized_batch",
    "read_roadmap_progress_update",
    "update_roadmap_after_execution",
    "validate_roadmap_progress_update",
    "write_roadmap_progress_update",
]
