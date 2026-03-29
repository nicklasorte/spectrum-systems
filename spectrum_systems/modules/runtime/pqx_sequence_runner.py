"""Deterministic, fail-closed sequential PQX slice runner with persisted resumable state."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Callable

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.prompt_queue.queue_models import iso_now, utc_now
from spectrum_systems.modules.runtime.pqx_bundle_state import (
    PQXBundleStateError,
    block_step as bundle_block_step,
    initialize_bundle_state,
    load_bundle_state,
    mark_bundle_complete,
    mark_step_complete,
    save_bundle_state,
)


class PQXSequenceRunnerError(ValueError):
    """Raised when sequence-run orchestration fails closed."""


SliceExecutor = Callable[[dict], dict]


def _validate_slice_requests(slice_requests: list[dict]) -> None:
    if not isinstance(slice_requests, list) or not slice_requests:
        raise PQXSequenceRunnerError("slice_requests must be a non-empty ordered list.")

    seen: set[str] = set()
    for index, request in enumerate(slice_requests):
        if not isinstance(request, dict):
            raise PQXSequenceRunnerError(f"slice request at index {index} must be an object.")
        slice_id = request.get("slice_id")
        trace_id = request.get("trace_id")
        if not isinstance(slice_id, str) or not slice_id:
            raise PQXSequenceRunnerError(f"slice request at index {index} missing required slice_id.")
        if not isinstance(trace_id, str) or not trace_id:
            raise PQXSequenceRunnerError(f"slice request '{slice_id}' missing required trace_id.")
        if slice_id in seen:
            raise PQXSequenceRunnerError(f"duplicate slice_id not allowed: {slice_id}")
        seen.add(slice_id)


def _validate_state_contract(state: dict) -> None:
    try:
        validate_artifact(state, "prompt_queue_sequence_run")
    except Exception as exc:  # fail-closed contract boundary
        raise PQXSequenceRunnerError(f"invalid prompt_queue_sequence_run artifact: {exc}") from exc


def _build_initial_state(*, queue_run_id: str, run_id: str, trace_id: str, slice_requests: list[dict], now: str) -> dict:
    requested = [entry["slice_id"] for entry in slice_requests]
    return {
        "schema_version": "1.0.0",
        "queue_run_id": queue_run_id,
        "run_id": run_id,
        "trace_id": trace_id,
        "status": "pending",
        "created_at": now,
        "updated_at": now,
        "requested_slice_ids": requested,
        "completed_slice_ids": [],
        "failed_slice_ids": [],
        "current_slice_id": None,
        "prior_slice_ref": None,
        "next_slice_ref": requested[0] if requested else None,
        "execution_history": [],
        "blocked_reason": None,
        "resume_token": f"resume:{queue_run_id}:0",
    }


def _persist_and_reload_exact(state: dict, state_path: Path) -> dict:
    _validate_state_contract(state)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    reloaded = json.loads(state_path.read_text(encoding="utf-8"))
    _validate_state_contract(reloaded)
    if reloaded != state:
        raise PQXSequenceRunnerError("persisted-reload mismatch detected for prompt_queue_sequence_run state")
    return reloaded


def _verify_continuity(state: dict, slice_requests: list[dict]) -> None:
    requested_ids = [entry["slice_id"] for entry in slice_requests]
    trace_by_slice = {entry["slice_id"]: entry["trace_id"] for entry in slice_requests}

    if state.get("requested_slice_ids") != requested_ids:
        raise PQXSequenceRunnerError("persisted requested_slice_ids do not match requested execution order")

    completed = state.get("completed_slice_ids", [])
    failed = state.get("failed_slice_ids", [])
    history = state.get("execution_history", [])
    queue_run_id = state.get("queue_run_id")
    run_id = state.get("run_id")

    if set(completed) & set(failed):
        raise PQXSequenceRunnerError("slice cannot be both completed and failed")

    prev_ref = None
    history_completed: list[str] = []
    history_failed: list[str] = []
    for index, record in enumerate(history):
        if record.get("queue_run_id") != queue_run_id:
            raise PQXSequenceRunnerError("all slices must inherit identical queue_run_id")
        if record.get("run_id") != run_id:
            raise PQXSequenceRunnerError("all slices must inherit stable batch run_id")
        slice_id = record.get("slice_id")
        if slice_id not in requested_ids:
            raise PQXSequenceRunnerError("execution_history contains unknown slice_id")
        expected_trace = trace_by_slice.get(slice_id)
        if record.get("trace_id") != expected_trace:
            raise PQXSequenceRunnerError("per-slice trace linkage mismatch detected")

        expected_parent = prev_ref if index > 0 else None
        if record.get("parent_execution_ref") != expected_parent:
            raise PQXSequenceRunnerError("parent-child execution order continuity mismatch")

        prev_ref = record.get("execution_ref")
        if record.get("status") == "success":
            history_completed.append(slice_id)
        else:
            history_failed.append(slice_id)

    if completed != history_completed:
        raise PQXSequenceRunnerError("completed_slice_ids mismatch with execution_history success entries")
    if failed != history_failed:
        raise PQXSequenceRunnerError("failed_slice_ids mismatch with execution_history failed entries")


def _next_pending_slice(requested_ids: list[str], completed_ids: list[str], failed_ids: list[str]) -> str | None:
    done = set(completed_ids) | set(failed_ids)
    for slice_id in requested_ids:
        if slice_id not in done:
            return slice_id
    return None


def _default_bundle_plan(slice_requests: list[dict], bundle_id: str) -> list[dict]:
    return [{"bundle_id": bundle_id, "step_ids": [entry["slice_id"] for entry in slice_requests], "depends_on": []}]


def _load_or_initialize_bundle_state(
    *,
    bundle_state_path: Path,
    bundle_plan: list[dict],
    queue_run_id: str,
    run_id: str,
    roadmap_authority_ref: str,
    execution_plan_ref: str,
    clock,
    resume: bool,
) -> dict:
    if bundle_state_path.exists():
        return load_bundle_state(bundle_state_path, bundle_plan=bundle_plan)
    if resume:
        raise PQXSequenceRunnerError("resume requested but pqx_bundle_state artifact is missing")

    try:
        initialized = initialize_bundle_state(
            bundle_plan=bundle_plan,
            run_id=run_id,
            sequence_run_id=queue_run_id,
            roadmap_authority_ref=roadmap_authority_ref,
            execution_plan_ref=execution_plan_ref,
            now=iso_now(clock),
        )
        return save_bundle_state(initialized, bundle_state_path, bundle_plan=bundle_plan)
    except PQXBundleStateError as exc:
        raise PQXSequenceRunnerError(str(exc)) from exc


def execute_sequence_run(
    *,
    slice_requests: list[dict],
    state_path: str | Path,
    queue_run_id: str,
    run_id: str,
    trace_id: str,
    execute_slice: SliceExecutor | None = None,
    resume: bool = False,
    rerun_completed: bool = False,
    max_slices: int | None = None,
    bundle_state_path: str | Path | None = None,
    bundle_id: str = "BUNDLE-03",
    bundle_plan: list[dict] | None = None,
    roadmap_authority_ref: str = "docs/roadmaps/system_roadmap.md",
    execution_plan_ref: str = "docs/roadmaps/execution_bundles.md",
    clock=utc_now,
) -> dict:
    """Run a narrow deterministic sequential PQX batch (2–3 slices) with persistent resumable state."""

    if not isinstance(queue_run_id, str) or not queue_run_id:
        raise PQXSequenceRunnerError("queue_run_id is required")
    if not isinstance(run_id, str) or not run_id:
        raise PQXSequenceRunnerError("run_id is required")
    if not isinstance(trace_id, str) or not trace_id:
        raise PQXSequenceRunnerError("trace_id is required")

    _validate_slice_requests(slice_requests)
    state_path = Path(state_path)
    resolved_bundle_plan = bundle_plan or _default_bundle_plan(slice_requests, bundle_id)
    resolved_bundle_state_path = Path(bundle_state_path) if bundle_state_path is not None else None
    bundle_state = None

    executor = execute_slice or (lambda payload: {"execution_status": "success"})

    if resume:
        if not state_path.exists():
            raise PQXSequenceRunnerError("resume requested but state artifact is missing")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        _validate_state_contract(state)
        if state["queue_run_id"] != queue_run_id or state["run_id"] != run_id or state["trace_id"] != trace_id:
            raise PQXSequenceRunnerError("resume identity mismatch for queue_run_id/run_id/trace_id")
    else:
        now = iso_now(clock)
        state = _build_initial_state(
            queue_run_id=queue_run_id,
            run_id=run_id,
            trace_id=trace_id,
            slice_requests=slice_requests,
            now=now,
        )

    _verify_continuity(state, slice_requests)
    state = _persist_and_reload_exact(state, state_path)

    if resolved_bundle_state_path is not None:
        bundle_state = _load_or_initialize_bundle_state(
            bundle_state_path=resolved_bundle_state_path,
            bundle_plan=resolved_bundle_plan,
            queue_run_id=queue_run_id,
            run_id=run_id,
            roadmap_authority_ref=roadmap_authority_ref,
            execution_plan_ref=execution_plan_ref,
            clock=clock,
            resume=resume,
        )

    requested_ids = state["requested_slice_ids"]
    executed_this_call = 0
    while True:
        _verify_continuity(state, slice_requests)
        next_slice_id = _next_pending_slice(requested_ids, state["completed_slice_ids"], state["failed_slice_ids"])
        if next_slice_id is None:
            state["status"] = "completed"
            state["current_slice_id"] = None
            state["next_slice_ref"] = None
            state["blocked_reason"] = None
            state["updated_at"] = iso_now(clock)
            state["resume_token"] = f"resume:{queue_run_id}:{len(state['completed_slice_ids'])}"
            persisted = _persist_and_reload_exact(state, state_path)
            if bundle_state is not None and bundle_state["active_bundle_id"] not in bundle_state["completed_bundle_ids"]:
                try:
                    bundle_state = mark_bundle_complete(
                        bundle_state,
                        resolved_bundle_plan,
                        bundle_id=bundle_state["active_bundle_id"],
                        now=iso_now(clock),
                    )
                    save_bundle_state(bundle_state, resolved_bundle_state_path, bundle_plan=resolved_bundle_plan)
                except PQXBundleStateError as exc:
                    raise PQXSequenceRunnerError(str(exc)) from exc
            return persisted

        if max_slices is not None and executed_this_call >= max_slices:
            state["status"] = "running"
            state["current_slice_id"] = next_slice_id
            state["next_slice_ref"] = next_slice_id
            state["blocked_reason"] = None
            state["updated_at"] = iso_now(clock)
            return _persist_and_reload_exact(state, state_path)

        already_completed = next_slice_id in state["completed_slice_ids"]
        if already_completed and not rerun_completed:
            raise PQXSequenceRunnerError("invalid transition: completed slice selected for rerun without explicit override")

        request = next(entry for entry in slice_requests if entry["slice_id"] == next_slice_id)
        parent_ref = state["execution_history"][-1]["execution_ref"] if state["execution_history"] else None
        attempt = 1 + sum(1 for row in state["execution_history"] if row["slice_id"] == next_slice_id)
        execution_ref = f"exec:{queue_run_id}:{next_slice_id}:{attempt}"
        started_at = iso_now(clock)

        state["status"] = "running"
        state["current_slice_id"] = next_slice_id
        state["next_slice_ref"] = next_slice_id
        state["updated_at"] = started_at
        state = _persist_and_reload_exact(state, state_path)

        payload = {
            "queue_run_id": queue_run_id,
            "run_id": run_id,
            "trace_id": request["trace_id"],
            "slice_id": next_slice_id,
            "parent_execution_ref": parent_ref,
            "execution_ref": execution_ref,
            "resume_token": state["resume_token"],
        }
        result = executor(deepcopy(payload))
        if not isinstance(result, dict):
            raise PQXSequenceRunnerError("slice executor must return an object result")

        child_queue_run_id = result.get("queue_run_id", queue_run_id)
        child_run_id = result.get("run_id", run_id)
        child_trace_id = result.get("trace_id", request["trace_id"])
        child_parent_ref = result.get("parent_execution_ref", parent_ref)

        if child_queue_run_id != queue_run_id:
            raise PQXSequenceRunnerError("child continuity mismatch: queue_run_id changed")
        if child_run_id != run_id:
            raise PQXSequenceRunnerError("child continuity mismatch: run_id changed")
        if child_trace_id != request["trace_id"]:
            raise PQXSequenceRunnerError("child continuity mismatch: trace_id changed")
        if child_parent_ref != parent_ref:
            raise PQXSequenceRunnerError("child continuity mismatch: parent_execution_ref changed")

        execution_status = result.get("execution_status")
        if execution_status not in {"success", "failed"}:
            raise PQXSequenceRunnerError("slice executor must return execution_status of success or failed")

        completed_at = iso_now(clock)
        record = {
            "execution_ref": execution_ref,
            "queue_run_id": queue_run_id,
            "run_id": run_id,
            "trace_id": request["trace_id"],
            "slice_id": next_slice_id,
            "status": execution_status,
            "parent_execution_ref": parent_ref,
            "started_at": started_at,
            "completed_at": completed_at,
            "error": result.get("error"),
        }
        state["execution_history"].append(record)
        state["prior_slice_ref"] = execution_ref

        if execution_status == "success":
            state["completed_slice_ids"].append(next_slice_id)
            state["status"] = "running"
            state["blocked_reason"] = None
            if bundle_state is not None:
                try:
                    bundle_state = mark_step_complete(
                        bundle_state,
                        resolved_bundle_plan,
                        step_id=next_slice_id,
                        artifact_refs=[],
                        now=completed_at,
                    )
                    save_bundle_state(bundle_state, resolved_bundle_state_path, bundle_plan=resolved_bundle_plan)
                except PQXBundleStateError as exc:
                    raise PQXSequenceRunnerError(str(exc)) from exc
        else:
            state["failed_slice_ids"].append(next_slice_id)
            state["status"] = "failed"
            state["blocked_reason"] = result.get("error") or "slice_execution_failed"
            if bundle_state is not None:
                try:
                    bundle_state = bundle_block_step(
                        bundle_state,
                        resolved_bundle_plan,
                        step_id=next_slice_id,
                        now=completed_at,
                    )
                    save_bundle_state(bundle_state, resolved_bundle_state_path, bundle_plan=resolved_bundle_plan)
                except PQXBundleStateError as exc:
                    raise PQXSequenceRunnerError(str(exc)) from exc

        state["current_slice_id"] = None
        state["next_slice_ref"] = _next_pending_slice(requested_ids, state["completed_slice_ids"], state["failed_slice_ids"])
        state["updated_at"] = completed_at
        state["resume_token"] = f"resume:{queue_run_id}:{len(state['completed_slice_ids'])}"
        state = _persist_and_reload_exact(state, state_path)
        executed_this_call += 1

        if execution_status != "success":
            return state
