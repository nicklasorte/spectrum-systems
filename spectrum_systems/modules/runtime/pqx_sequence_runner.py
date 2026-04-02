"""Deterministic, fail-closed sequential PQX slice runner with persisted resumable state."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Callable

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.prompt_queue.queue_models import iso_now, utc_now
from spectrum_systems.modules.runtime.pqx_slice_runner import run_pqx_slice
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


def _default_control_surface_gap_visibility() -> dict:
    return {
        "control_surface_gap_packet_ref": None,
        "control_surface_gap_packet_consumed": False,
        "prioritized_control_surface_gaps": [],
        "pqx_gap_work_items": [],
        "control_surface_gap_influence": {
            "influenced_execution_block": False,
            "influenced_next_step_selection": False,
            "influenced_priority_ordering": False,
            "influenced_transition_decision": False,
            "reason_codes": [],
            "control_surface_blocking_reason_refs": [],
        },
    }


def _validate_control_surface_gap_visibility(visibility: dict) -> dict:
    if not isinstance(visibility, dict):
        raise PQXSequenceRunnerError("control_surface_gap_visibility must be an object")
    required_top = (
        "control_surface_gap_packet_ref",
        "control_surface_gap_packet_consumed",
        "prioritized_control_surface_gaps",
        "pqx_gap_work_items",
        "control_surface_gap_influence",
    )
    missing = [field for field in required_top if field not in visibility]
    if missing:
        raise PQXSequenceRunnerError(
            f"control_surface_gap_visibility missing required fields: {', '.join(missing)}"
        )
    influence = visibility["control_surface_gap_influence"]
    if not isinstance(influence, dict):
        raise PQXSequenceRunnerError("control_surface_gap_visibility.control_surface_gap_influence must be an object")
    return visibility


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
        "schema_version": "1.4.0",
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
        "continuation_records": [],
        "lineage": {"prior_run_id": None, "prior_trace_id": None},
        "certification_complete_by_slice": {slice_id: False for slice_id in requested},
        "audit_complete_by_slice": {slice_id: False for slice_id in requested},
        "blocked_continuation_context": None,
        "replay_verification": {"status": "not_run", "replay_record_ref": None},
        "review_checkpoint_status": {
            "slice_1_optional_review": "not_required",
            "slice_2_required_review": "required_pending",
            "slice_3_strict_review": "required_pending",
        },
        "review_artifact_refs": [],
        "sequence_budget_status": "not_started",
        "sequence_budget_ref": None,
        "chain_certification_status": "pending",
        "chain_certification_refs": [],
        "bundle_readiness_decision": {"ready": True, "reason": "initial readiness satisfied"},
        "bundle_certification_status": "pending",
        "bundle_certification_ref": None,
        "bundle_audit_status": "pending",
        "bundle_audit_ref": None,
        "unresolved_fix_ids": [],
        "blocked_reason": None,
        "resume_token": f"resume:{queue_run_id}:0",
        "control_surface_gap_visibility": {
            "by_slice": {},
            "summary": _default_control_surface_gap_visibility(),
        },
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
    continuation_by_next = {entry["next_step_id"]: entry for entry in state.get("continuation_records", [])}
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
            if index > 0:
                continuation = continuation_by_next.get(slice_id)
                if continuation is None:
                    raise PQXSequenceRunnerError("missing continuation record for successful non-initial slice")
                previous = history[index - 1]
                if continuation.get("prior_step_id") != previous.get("slice_id"):
                    raise PQXSequenceRunnerError("continuation record prior_step_id mismatch")
                if continuation.get("prior_run_id") != previous.get("run_id"):
                    raise PQXSequenceRunnerError("continuation record prior_run_id mismatch")
                if continuation.get("prior_trace_id") != previous.get("trace_id"):
                    raise PQXSequenceRunnerError("continuation record prior_trace_id mismatch")
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


def _build_continuation_record(*, prior_record: dict, next_slice_id: str, now: str) -> dict:
    continuation = {
        "artifact_id": f"cont:{prior_record['queue_run_id']}:{prior_record['slice_id']}:{next_slice_id}",
        "artifact_type": "pqx_slice_continuation_record",
        "schema_version": "1.0.0",
        "prior_step_id": prior_record["slice_id"],
        "next_step_id": next_slice_id,
        "prior_run_id": prior_record["run_id"],
        "prior_trace_id": prior_record["trace_id"],
        "prior_slice_execution_record_ref": prior_record["slice_execution_record_ref"],
        "prior_certification_ref": prior_record["certification_ref"],
        "prior_audit_bundle_ref": prior_record["audit_bundle_ref"],
        "continuation_status": "ready",
        "continuation_decision": "allow",
        "continuation_reasons": [
            "prior slice emitted canonical execution, certification, and audit artifacts",
            "lineage continuity satisfied for run_id and trace_id",
        ],
        "created_at": now,
    }
    validate_artifact(continuation, "pqx_slice_continuation_record")
    return continuation


def _apply_continuation_block(*, state: dict, queue_run_id: str, next_slice_id: str, block_type: str, reason: str, now: str) -> None:
    state["status"] = "blocked"
    state["blocked_reason"] = reason
    state["blocked_continuation_context"] = {
        "block_type": block_type,
        "reason": reason,
        "next_slice_id": next_slice_id,
    }
    state["current_slice_id"] = None
    state["next_slice_ref"] = next_slice_id
    state["updated_at"] = now
    state["resume_token"] = f"resume:{queue_run_id}:{len(state['completed_slice_ids'])}"


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
    review_results_by_slice: dict[str, dict] | None = None,
    sequence_budget_thresholds: dict | None = None,
    canary_control: dict | None = None,
) -> dict:
    """Run a narrow deterministic sequential PQX batch (2–3 slices) with persistent resumable state."""

    if not isinstance(queue_run_id, str) or not queue_run_id:
        raise PQXSequenceRunnerError("queue_run_id is required")
    if not isinstance(run_id, str) or not run_id:
        raise PQXSequenceRunnerError("run_id is required")
    if not isinstance(trace_id, str) or not trace_id:
        raise PQXSequenceRunnerError("trace_id is required")

    _validate_slice_requests(slice_requests)
    review_results = review_results_by_slice or {}
    enforce_review_policy = review_results_by_slice is not None
    state_path = Path(state_path)
    resolved_bundle_plan = bundle_plan or _default_bundle_plan(slice_requests, bundle_id)
    resolved_bundle_state_path = Path(bundle_state_path) if bundle_state_path is not None else None
    bundle_state = None

    if execute_slice is None:

        def _default_executor(payload: dict) -> dict:
            slice_id = str(payload.get("slice_id", ""))
            if slice_id.startswith("AI-"):
                canonical_step_id = slice_id
            elif slice_id == "PQX-QUEUE-01":
                canonical_step_id = "AI-01"
            elif slice_id == "PQX-QUEUE-02":
                canonical_step_id = "AI-02"
            else:
                canonical_step_id = "TRUST-01"
            step_result = run_pqx_slice(
                step_id=canonical_step_id,
                roadmap_path=Path("docs/roadmap/system_roadmap.md"),
                state_path=Path(state_path).parent / "pqx_state.json",
                runs_root=Path(state_path).parent / "pqx_slice_runs",
                clock=clock,
                pqx_output_text=f"deterministic output for {payload['slice_id']}",
            )
            if step_result.get("status") != "complete":
                return {
                    "execution_status": "failed",
                    "error": step_result.get("reason") or step_result.get("block_type", "blocked"),
                }
            return {
                "execution_status": "success",
                "slice_execution_record": step_result.get("slice_execution_record"),
                "done_certification_record": step_result.get("done_certification_record"),
                "pqx_slice_audit_bundle": step_result.get("pqx_slice_audit_bundle"),
                "certification_complete": step_result.get("certification_status") == "certified",
                "audit_complete": bool(step_result.get("pqx_slice_audit_bundle")),
                "control_surface_gap_visibility": step_result.get("control_surface_gap_visibility"),
            }

        executor = _default_executor
    else:
        executor = execute_slice

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
    _verify_continuity(state, slice_requests)

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
    budget_thresholds = sequence_budget_thresholds or {"max_failed_slices": 1, "max_cumulative_severity": 5}
    canary = canary_control or {"status": "not_applicable", "frozen_slice_ids": []}
    executed_this_call = 0
    while True:
        _verify_continuity(state, slice_requests)
        next_slice_id = _next_pending_slice(requested_ids, state["completed_slice_ids"], state["failed_slice_ids"])
        if next_slice_id is None:
            if len(requested_ids) >= 3:
                first_three = requested_ids[:3]
                all_three_certified = all(state["certification_complete_by_slice"].get(sid, False) for sid in first_three)
                reviews_satisfied = True
                if enforce_review_policy:
                    reviews_satisfied = (
                        state["review_checkpoint_status"]["slice_2_required_review"] == "satisfied"
                        and state["review_checkpoint_status"]["slice_3_strict_review"] == "satisfied"
                    )
                chain_status = "certified" if all_three_certified and reviews_satisfied and not state["unresolved_fix_ids"] else "blocked"
                if chain_status != "certified":
                    state["status"] = "blocked"
                    state["chain_certification_status"] = "blocked"
                    state["blocked_reason"] = "chain certification blocked: reviews/fixes/certification incomplete"
                    return _persist_and_reload_exact(state, state_path)
                chain_ref = f"{queue_run_id}:chain-3"
                if chain_ref not in state["chain_certification_refs"]:
                    state["chain_certification_refs"].append(chain_ref)
                state["chain_certification_status"] = "certified"
            else:
                state["chain_certification_status"] = "pending"
            if not state.get("bundle_readiness_decision", {}).get("ready", False):
                state["status"] = "blocked"
                state["bundle_certification_status"] = "failed"
                state["blocked_reason"] = "bundle readiness unresolved"
                return _persist_and_reload_exact(state, state_path)
            state["bundle_certification_status"] = "certified"
            state["bundle_certification_ref"] = f"{queue_run_id}:bundle-cert"
            history_refs = [row.get("slice_execution_record_ref") for row in state["execution_history"] if row.get("slice_execution_record_ref")]
            if not history_refs:
                state["status"] = "blocked"
                state["bundle_audit_status"] = "missing"
                state["blocked_reason"] = "missing bundle audit artifacts"
                return _persist_and_reload_exact(state, state_path)
            state["bundle_audit_status"] = "synthesized"
            state["bundle_audit_ref"] = f"{queue_run_id}:bundle-audit"
            state["status"] = "completed"
            state["current_slice_id"] = None
            state["next_slice_ref"] = None
            state["blocked_reason"] = None
            state["blocked_continuation_context"] = None
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
            state["blocked_continuation_context"] = None
            state["updated_at"] = iso_now(clock)
            return _persist_and_reload_exact(state, state_path)

        already_completed = next_slice_id in state["completed_slice_ids"]
        if already_completed and not rerun_completed:
            raise PQXSequenceRunnerError("invalid transition: completed slice selected for rerun without explicit override")

        request = next(entry for entry in slice_requests if entry["slice_id"] == next_slice_id)
        if canary.get("status") == "frozen" and next_slice_id in set(canary.get("frozen_slice_ids", [])):
            _apply_continuation_block(
                state=state,
                queue_run_id=queue_run_id,
                next_slice_id=next_slice_id,
                block_type="CANARY_FROZEN",
                reason="canary rollout failure froze this slice path",
                now=iso_now(clock),
            )
            return _persist_and_reload_exact(state, state_path)
        current_index = requested_ids.index(next_slice_id)
        state["bundle_readiness_decision"] = {
            "ready": len(state["unresolved_fix_ids"]) == 0,
            "reason": "dependencies/artifacts valid and no blocking findings"
            if len(state["unresolved_fix_ids"]) == 0
            else "blocking findings unresolved",
        }
        if not state["bundle_readiness_decision"]["ready"]:
            state["status"] = "blocked"
            state["blocked_reason"] = "bundle readiness gate blocked"
            return _persist_and_reload_exact(state, state_path)
        if current_index > 0:
            prior_slice_id = requested_ids[current_index - 1]
            prior_success = [
                row for row in state["execution_history"] if row["slice_id"] == prior_slice_id and row["status"] == "success"
            ]
            if not prior_success:
                _apply_continuation_block(
                    state=state,
                    queue_run_id=queue_run_id,
                    next_slice_id=next_slice_id,
                    block_type="PRIOR_SLICE_NOT_GOVERNED",
                    reason="prior slice not completed successfully through canonical path",
                    now=iso_now(clock),
                )
                return _persist_and_reload_exact(state, state_path)
            prior_record = prior_success[-1]
            if not prior_record.get("certification_complete") or not prior_record.get("audit_complete"):
                _apply_continuation_block(
                    state=state,
                    queue_run_id=queue_run_id,
                    next_slice_id=next_slice_id,
                    block_type="PRIOR_SLICE_NOT_GOVERNED",
                    reason="prior slice missing required certification or audit completion",
                    now=iso_now(clock),
                )
                return _persist_and_reload_exact(state, state_path)
            try:
                continuation = _build_continuation_record(prior_record=prior_record, next_slice_id=next_slice_id, now=iso_now(clock))
            except Exception as exc:
                _apply_continuation_block(
                    state=state,
                    queue_run_id=queue_run_id,
                    next_slice_id=next_slice_id,
                    block_type="INVALID_SLICE_CONTINUATION",
                    reason=f"invalid continuation record: {exc}",
                    now=iso_now(clock),
                )
                return _persist_and_reload_exact(state, state_path)
            existing = [entry for entry in state["continuation_records"] if entry["next_step_id"] == next_slice_id]
            if existing and existing[-1] != continuation:
                _apply_continuation_block(
                    state=state,
                    queue_run_id=queue_run_id,
                    next_slice_id=next_slice_id,
                    block_type="CONTINUATION_STATE_MISMATCH",
                    reason="persisted continuation record mismatches governed prior artifacts",
                    now=iso_now(clock),
                )
                return _persist_and_reload_exact(state, state_path)
            if not existing:
                state["continuation_records"].append(continuation)
                state["lineage"] = {
                    "prior_run_id": continuation["prior_run_id"],
                    "prior_trace_id": continuation["prior_trace_id"],
                }

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
        continuation_record_id = None
        if current_index > 0:
            continuation_record_id = next(
                (entry["artifact_id"] for entry in state["continuation_records"] if entry["next_step_id"] == next_slice_id),
                None,
            )
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
            "slice_execution_record_ref": result.get("slice_execution_record"),
            "certification_ref": result.get("done_certification_record"),
            "audit_bundle_ref": result.get("pqx_slice_audit_bundle"),
            "certification_complete": bool(result.get("certification_complete") or result.get("done_certification_record")),
            "audit_complete": bool(result.get("audit_complete") or result.get("pqx_slice_audit_bundle")),
            "continuation_record_id": continuation_record_id,
            "control_surface_gap_visibility": _default_control_surface_gap_visibility(),
        }
        raw_visibility = result.get("control_surface_gap_visibility")
        if raw_visibility is not None:
            record["control_surface_gap_visibility"] = _validate_control_surface_gap_visibility(raw_visibility)
        elif result.get("control_surface_gap_packet_ref") is not None:
            raise PQXSequenceRunnerError(
                "missing control_surface_gap_visibility for slice result carrying control_surface_gap_packet_ref"
            )
        state["execution_history"].append(record)
        state_visibility = state.get("control_surface_gap_visibility")
        if not isinstance(state_visibility, dict):
            raise PQXSequenceRunnerError("prompt_queue_sequence_run missing control_surface_gap_visibility projection")
        by_slice = state_visibility.get("by_slice")
        if not isinstance(by_slice, dict):
            raise PQXSequenceRunnerError("prompt_queue_sequence_run control_surface_gap_visibility.by_slice must be object")
        by_slice[next_slice_id] = record["control_surface_gap_visibility"]
        consumed_entries = [
            entry
            for _, entry in sorted(by_slice.items(), key=lambda pair: pair[0])
            if isinstance(entry, dict) and entry.get("control_surface_gap_packet_consumed") is True
        ]
        if consumed_entries:
            summary = consumed_entries[-1]
        else:
            summary = _default_control_surface_gap_visibility()
        state["control_surface_gap_visibility"] = {"by_slice": by_slice, "summary": summary}
        state["prior_slice_ref"] = execution_ref

        if execution_status == "success":
            state["completed_slice_ids"].append(next_slice_id)
            state["status"] = "running"
            state["blocked_reason"] = None
            state["blocked_continuation_context"] = None
            state["certification_complete_by_slice"][next_slice_id] = record["certification_complete"]
            state["audit_complete_by_slice"][next_slice_id] = record["audit_complete"]
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
            if current_index == 0 and enforce_review_policy:
                review = review_results.get(next_slice_id)
                if review is None:
                    state["review_checkpoint_status"]["slice_1_optional_review"] = "not_required"
                elif review.get("has_blocking_findings"):
                    state["review_checkpoint_status"]["slice_1_optional_review"] = "blocked"
                    state["status"] = "blocked"
                    state["blocked_reason"] = "optional slice-1 review contains blocking findings"
                    return _persist_and_reload_exact(state, state_path)
                else:
                    state["review_checkpoint_status"]["slice_1_optional_review"] = "satisfied"
                    state["review_artifact_refs"].append(str(review.get("review_id", f"review:{next_slice_id}")))
            elif current_index == 1 and enforce_review_policy:
                review = review_results.get(next_slice_id)
                if review is None:
                    state["review_checkpoint_status"]["slice_2_required_review"] = "missing"
                    state["status"] = "blocked"
                    state["chain_certification_status"] = "blocked"
                    state["blocked_reason"] = "missing required review after slice 2"
                    return _persist_and_reload_exact(state, state_path)
                if review.get("has_blocking_findings"):
                    state["review_checkpoint_status"]["slice_2_required_review"] = "blocked"
                    state["status"] = "blocked"
                    state["chain_certification_status"] = "blocked"
                    state["blocked_reason"] = "blocking findings after slice 2 review"
                    state["unresolved_fix_ids"].extend(review.get("pending_fix_ids", []))
                    state["bundle_readiness_decision"] = {"ready": False, "reason": "blocking findings unresolved"}
                    return _persist_and_reload_exact(state, state_path)
                state["review_checkpoint_status"]["slice_2_required_review"] = "satisfied"
                state["review_artifact_refs"].append(str(review.get("review_id", f"review:{next_slice_id}")))
            elif current_index == 2 and enforce_review_policy:
                review = review_results.get(next_slice_id)
                if review is None:
                    state["review_checkpoint_status"]["slice_3_strict_review"] = "missing"
                    state["status"] = "blocked"
                    state["chain_certification_status"] = "blocked"
                    state["blocked_reason"] = "missing strict review after slice 3"
                    return _persist_and_reload_exact(state, state_path)
                if review.get("overall_disposition") != "approved" or review.get("has_blocking_findings"):
                    state["review_checkpoint_status"]["slice_3_strict_review"] = "blocked"
                    state["status"] = "blocked"
                    state["chain_certification_status"] = "blocked"
                    state["blocked_reason"] = "strict slice-3 review did not pass"
                    state["unresolved_fix_ids"].extend(review.get("pending_fix_ids", []))
                    state["bundle_readiness_decision"] = {"ready": False, "reason": "blocking findings unresolved"}
                    return _persist_and_reload_exact(state, state_path)
                state["review_checkpoint_status"]["slice_3_strict_review"] = "satisfied"
                state["review_artifact_refs"].append(str(review.get("review_id", f"review:{next_slice_id}")))
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

        failure_rows = [row for row in state["execution_history"] if row["status"] == "failed"]
        severity_total = sum(1 if not row.get("error") else 2 for row in failure_rows)
        budget = {
            "schema_version": "1.0.0",
            "artifact_type": "pqx_sequence_budget",
            "sequence_id": queue_run_id,
            "thresholds": {
                "max_failed_slices": int(budget_thresholds.get("max_failed_slices", 1)),
                "max_cumulative_severity": int(budget_thresholds.get("max_cumulative_severity", 5)),
            },
            "slice_failures": [
                {
                    "slice_id": row["slice_id"],
                    "failure_count": 1 if row["status"] == "failed" else 0,
                    "failure_severity": 0 if row["status"] != "failed" else (1 if not row.get("error") else 2),
                }
                for row in state["execution_history"]
            ],
            "cumulative_failure_severity": severity_total,
            "threshold_breached": len(failure_rows) > int(budget_thresholds.get("max_failed_slices", 1))
            or severity_total > int(budget_thresholds.get("max_cumulative_severity", 5)),
            "created_at": iso_now(clock),
        }
        budget["status"] = "exceeded_budget" if budget["threshold_breached"] else "within_budget"
        validate_artifact(budget, "pqx_sequence_budget")
        state["sequence_budget_ref"] = f"{queue_run_id}:sequence-budget"
        state["sequence_budget_status"] = budget["status"]
        if budget["threshold_breached"]:
            state["status"] = "blocked"
            state["blocked_reason"] = "sequence failure budget exceeded"
            return _persist_and_reload_exact(state, state_path)

        state["current_slice_id"] = None
        state["next_slice_ref"] = _next_pending_slice(requested_ids, state["completed_slice_ids"], state["failed_slice_ids"])
        state["updated_at"] = completed_at
        state["resume_token"] = f"resume:{queue_run_id}:{len(state['completed_slice_ids'])}"
        state = _persist_and_reload_exact(state, state_path)
        executed_this_call += 1

        if execution_status != "success":
            return state


def verify_two_slice_replay(
    *,
    baseline_state_path: str | Path,
    replay_state_path: str | Path,
    output_path: str | Path,
    queue_run_id: str,
    run_id: str,
    trace_id: str,
    clock=utc_now,
) -> dict:
    baseline = json.loads(Path(baseline_state_path).read_text(encoding="utf-8"))
    replay = json.loads(Path(replay_state_path).read_text(encoding="utf-8"))
    _validate_state_contract(baseline)
    _validate_state_contract(replay)

    def _normalize_continuations(rows: list[dict]) -> list[dict]:
        normalized = []
        for row in rows:
            clone = {k: v for k, v in row.items() if k != "created_at"}
            normalized.append(clone)
        return normalized

    def _normalize_history(rows: list[dict]) -> list[dict]:
        keys = [
            "slice_id",
            "status",
            "trace_id",
            "slice_execution_record_ref",
            "certification_ref",
            "audit_bundle_ref",
            "certification_complete",
            "audit_complete",
            "continuation_record_id",
        ]
        return [{k: row.get(k) for k in keys} for row in rows]

    parity = (
        baseline["completed_slice_ids"] == replay["completed_slice_ids"]
        and _normalize_continuations(baseline["continuation_records"]) == _normalize_continuations(replay["continuation_records"])
        and _normalize_history(baseline["execution_history"]) == _normalize_history(replay["execution_history"])
        and baseline["certification_complete_by_slice"] == replay["certification_complete_by_slice"]
        and baseline["audit_complete_by_slice"] == replay["audit_complete_by_slice"]
        and baseline.get("chain_certification_status") == replay.get("chain_certification_status")
        and baseline.get("bundle_certification_status") == replay.get("bundle_certification_status")
    )
    replay_id = "queue-replay-" + hashlib.sha256(
        f"{queue_run_id}:{run_id}:{trace_id}:{baseline['resume_token']}:{replay['resume_token']}".encode("utf-8")
    ).hexdigest()
    record = {
        "replay_id": replay_id,
        "queue_id": queue_run_id,
        "checkpoint_ref": baseline_state_path if isinstance(baseline_state_path, str) else str(baseline_state_path),
        "input_refs": [
            baseline_state_path if isinstance(baseline_state_path, str) else str(baseline_state_path),
            replay_state_path if isinstance(replay_state_path, str) else str(replay_state_path),
        ],
        "replay_result_summary": {
            "replayed_step_id": "step-002",
            "decision_match": baseline["continuation_records"] == replay["continuation_records"],
            "state_match": baseline["completed_slice_ids"] == replay["completed_slice_ids"],
            "transition_match": _normalize_history(baseline["execution_history"]) == _normalize_history(replay["execution_history"]),
        },
        "parity_status": "match" if parity else "mismatch",
        "mismatch_summary": None if parity else "two-slice replay parity mismatch",
        "trace_id": trace_id,
        "timestamp": iso_now(clock),
    }
    validate_artifact(record, "prompt_queue_replay_record")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

    replay_status = "pass" if parity else "fail"
    baseline["replay_verification"] = {"status": replay_status, "replay_record_ref": str(output)}
    replay["replay_verification"] = {"status": replay_status, "replay_record_ref": str(output)}
    Path(baseline_state_path).write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
    Path(replay_state_path).write_text(json.dumps(replay, indent=2) + "\n", encoding="utf-8")

    if not parity:
        raise PQXSequenceRunnerError("two-slice replay verification failed closed")
    return record


def execute_bundle_sequence_run(
    *,
    bundle_id: str,
    bundle_state_path: str | Path,
    output_dir: str | Path,
    run_id: str,
    queue_run_id: str,
    trace_id: str,
    bundle_plan_path: str | Path = "docs/roadmaps/execution_bundles.md",
    execute_step: SliceExecutor | None = None,
    clock=utc_now,
) -> dict:
    """Additive bundle invocation path preserving existing step-oriented flows."""

    from spectrum_systems.modules.runtime.pqx_bundle_orchestrator import execute_bundle_run

    return execute_bundle_run(
        bundle_id=bundle_id,
        bundle_state_path=bundle_state_path,
        output_dir=output_dir,
        run_id=run_id,
        sequence_run_id=queue_run_id,
        trace_id=trace_id,
        bundle_plan_path=bundle_plan_path,
        execute_step=execute_step,
        clock=clock,
    )
