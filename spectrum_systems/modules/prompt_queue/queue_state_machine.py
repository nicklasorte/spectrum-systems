"""Deterministic state transitions and fail-closed queue loop orchestration."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Callable

from spectrum_systems.modules.prompt_queue.queue_artifact_io import (
    ArtifactValidationError,
    read_json_artifact,
    validate_queue_state,
    validate_replay_record,
    validate_resume_checkpoint,
)
from spectrum_systems.modules.prompt_queue.queue_manifest_validator import validate_queue_manifest
from spectrum_systems.modules.prompt_queue.queue_models import WorkItemStatus, iso_now, utc_now


class IllegalTransitionError(ValueError):
    """Raised when an illegal state transition is requested."""


_ALLOWED_TRANSITIONS = {
    WorkItemStatus.QUEUED.value: {WorkItemStatus.REVIEW_QUEUED.value, WorkItemStatus.BLOCKED.value},
    WorkItemStatus.REVIEW_QUEUED.value: {WorkItemStatus.REVIEW_RUNNING.value, WorkItemStatus.BLOCKED.value},
    WorkItemStatus.REVIEW_RUNNING.value: {
        WorkItemStatus.REVIEW_COMPLETE.value,
        WorkItemStatus.REVIEW_PROVIDER_FAILED.value,
        WorkItemStatus.BLOCKED.value,
    },
    WorkItemStatus.REVIEW_PROVIDER_FAILED.value: {
        WorkItemStatus.REVIEW_FALLBACK_RUNNING.value,
        WorkItemStatus.BLOCKED.value,
    },
    WorkItemStatus.REVIEW_FALLBACK_RUNNING.value: {
        WorkItemStatus.REVIEW_COMPLETE.value,
        WorkItemStatus.BLOCKED.value,
    },
    WorkItemStatus.REVIEW_COMPLETE.value: {WorkItemStatus.FINDINGS_PARSED.value},
    WorkItemStatus.FINDINGS_PARSED.value: {WorkItemStatus.REPAIR_PROMPT_GENERATED.value},
    WorkItemStatus.REPAIR_PROMPT_GENERATED.value: {WorkItemStatus.REPAIR_CHILD_CREATED.value},
    WorkItemStatus.REPAIR_CHILD_CREATED.value: {
        WorkItemStatus.EXECUTION_GATED.value,
        WorkItemStatus.BLOCKED.value,
    },
    WorkItemStatus.EXECUTION_GATED.value: {
        WorkItemStatus.RUNNABLE.value,
        WorkItemStatus.APPROVAL_REQUIRED.value,
        WorkItemStatus.BLOCKED.value,
    },
    WorkItemStatus.APPROVAL_REQUIRED.value: {
        WorkItemStatus.RUNNABLE.value,
        WorkItemStatus.BLOCKED.value,
    },
    WorkItemStatus.RUNNABLE.value: {WorkItemStatus.EXECUTING.value},
    WorkItemStatus.EXECUTING.value: {
        WorkItemStatus.EXECUTED_SUCCESS.value,
        WorkItemStatus.EXECUTED_FAILURE.value,
    },
    WorkItemStatus.EXECUTED_SUCCESS.value: {WorkItemStatus.COMPLETE.value},
    WorkItemStatus.EXECUTED_FAILURE.value: {
        WorkItemStatus.REVIEW_REQUIRED.value,
        WorkItemStatus.REENTRY_BLOCKED.value,
        WorkItemStatus.REENTRY_ELIGIBLE.value,
        WorkItemStatus.BLOCKED.value,
    },
    WorkItemStatus.REVIEW_REQUIRED.value: {
        WorkItemStatus.REVIEW_TRIGGERED.value,
        WorkItemStatus.BLOCKED.value,
    },
    WorkItemStatus.REENTRY_BLOCKED.value: {WorkItemStatus.BLOCKED.value},
    WorkItemStatus.REVIEW_TRIGGERED.value: {WorkItemStatus.REVIEW_INVOKING.value, WorkItemStatus.BLOCKED.value},
    WorkItemStatus.REVIEW_INVOKING.value: {
        WorkItemStatus.REVIEW_INVOCATION_SUCCEEDED.value,
        WorkItemStatus.REVIEW_INVOCATION_FAILED.value,
        WorkItemStatus.BLOCKED.value,
    },
    WorkItemStatus.REVIEW_INVOCATION_SUCCEEDED.value: {
        WorkItemStatus.FINDINGS_PARSED.value,
        WorkItemStatus.BLOCKED.value,
    },
    WorkItemStatus.REVIEW_INVOCATION_FAILED.value: set(),
    WorkItemStatus.REENTRY_ELIGIBLE.value: set(),
    WorkItemStatus.COMPLETE.value: set(),
    WorkItemStatus.BLOCKED.value: set(),
}


Clock = Callable


class QueueLoopError(ValueError):
    """Raised when a queue loop iteration cannot proceed deterministically."""


def _clone_queue_state(queue_state: dict) -> dict:
    clone = dict(queue_state)
    clone["work_items"] = [dict(item) for item in queue_state.get("work_items", [])]
    clone["step_results"] = [dict(result) for result in queue_state.get("step_results", [])]
    return clone


def _validate_loop_inputs(queue_state: dict, manifest: dict) -> tuple[dict, dict]:
    if not isinstance(queue_state, dict):
        raise QueueLoopError("invalid queue_state: expected object")
    if not isinstance(manifest, dict):
        raise QueueLoopError("missing manifest or invalid manifest object")

    try:
        normalized_queue_state = validate_queue_state(queue_state) or queue_state
    except ArtifactValidationError as exc:
        raise QueueLoopError(f"invalid queue_state: {exc}") from exc

    try:
        normalized_manifest = validate_queue_manifest(manifest)
    except ValueError as exc:
        raise QueueLoopError(f"missing manifest or invalid manifest: {exc}") from exc

    if normalized_queue_state.get("queue_id") != normalized_manifest.get("queue_id"):
        raise QueueLoopError("queue_state.queue_id must match manifest.queue_id")

    declared_total_steps = len(normalized_manifest["steps"])
    if normalized_queue_state.get("total_steps") != declared_total_steps:
        raise QueueLoopError("queue_state total_steps mismatch with manifest steps")

    step_results = normalized_queue_state.get("step_results", [])
    current_step_index = int(normalized_queue_state.get("current_step_index", -1))
    if len(step_results) != current_step_index:
        raise QueueLoopError("queue_state progression mismatch: current_step_index must equal len(step_results)")

    for index, result in enumerate(step_results):
        expected_step_id = normalized_manifest["steps"][index]["step_id"]
        if result.get("step_id") != expected_step_id:
            raise QueueLoopError("no step skipping permitted: step_results contain out-of-order step_id")
        if result.get("status") != "completed":
            raise QueueLoopError("no eligible next step: prior step not completed cleanly")

    return normalized_queue_state, normalized_manifest


def _select_next_eligible_step(queue_state: dict, manifest: dict) -> dict | None:
    status = queue_state.get("queue_status")
    if status in {"blocked", "completed"}:
        return None

    current_step_index = int(queue_state["current_step_index"])
    steps = manifest["steps"]
    if current_step_index == len(steps):
        return None
    if current_step_index < 0 or current_step_index > len(steps):
        raise QueueLoopError("next step cannot be determined: current_step_index out of bounds")

    return dict(steps[current_step_index])


def _build_step_execution_inputs(queue_state: dict, step: dict) -> tuple[dict, dict]:
    work_item_id = queue_state.get("active_work_item_id")
    if not isinstance(work_item_id, str) or not work_item_id:
        raise QueueLoopError("next step cannot be determined: active_work_item_id is required")

    work_item = None
    for candidate in queue_state.get("work_items", []):
        if candidate.get("work_item_id") == work_item_id:
            work_item = candidate
            break
    if work_item is None:
        raise QueueLoopError("next step cannot be determined: active work item missing from queue_state")

    metadata = step.get("metadata") or {}
    gating_decision_artifact = {
        "gating_decision_artifact_id": f"generated-gating-{step['step_id']}",
        "work_item_id": work_item_id,
        "parent_work_item_id": work_item.get("parent_work_item_id"),
        "repair_prompt_artifact_path": work_item.get("repair_prompt_artifact_path"),
        "findings_artifact_path": work_item.get("spawned_from_findings_artifact_path"),
        "review_artifact_path": work_item.get("spawned_from_review_artifact_path"),
        "repair_loop_generation": int(work_item.get("repair_loop_generation") or 0),
        "risk_level": work_item.get("risk_level"),
        "decision_status": "runnable",
        "decision_reason_code": "runnable_within_policy",
        "approval_required": False,
        "approval_present": False,
        "max_generation_allowed": 2,
        "gating_policy_id": "prompt_queue_execution_gating_policy.v1",
        "generated_at": iso_now(utc_now),
        "generator_version": "prompt_queue_execution_loop.v1",
        "blocking_conditions": [],
        "warnings": [],
        "lineage_summary": {
            "has_parent": bool(work_item.get("parent_work_item_id")),
            "has_repair_prompt_lineage": bool(work_item.get("repair_prompt_artifact_path")),
            "has_findings_lineage": bool(work_item.get("spawned_from_findings_artifact_path")),
            "has_review_lineage": bool(work_item.get("spawned_from_review_artifact_path")),
        },
        "source_queue_state_path": metadata.get("source_queue_state_path"),
    }

    execution_mode = metadata.get("execution_mode") or metadata.get("run_mode") or "simulated"
    execution_step = {
        "step_id": step["step_id"],
        "work_item_id": work_item_id,
        "execution_mode": execution_mode,
    }
    input_refs = {
        "gating_decision_artifact": gating_decision_artifact,
        "source_queue_state_path": metadata.get("source_queue_state_path"),
    }
    return execution_step, input_refs


def apply_transition_to_queue_state(queue_state: dict, transition_decision: dict, *, clock: Clock = utc_now) -> dict:
    """Apply a single transition decision to queue state deterministically."""
    if not isinstance(transition_decision, dict):
        raise QueueLoopError("transition decision missing")

    required = {"step_id", "source_decision_ref", "transition_action", "transition_status"}
    missing = sorted(required - set(transition_decision))
    if missing:
        raise QueueLoopError(f"transition decision missing required fields: {', '.join(missing)}")

    state = _clone_queue_state(queue_state)
    current_step_index = int(state["current_step_index"])
    total_steps = int(state["total_steps"])
    if current_step_index >= total_steps:
        raise QueueLoopError("multiple steps executed in one loop or queue already exhausted")

    expected_step_id = f"step-{current_step_index + 1:03d}"
    if transition_decision["step_id"] != expected_step_id:
        raise QueueLoopError("multiple steps executed in one loop or step_id mismatch")

    transition_action = transition_decision["transition_action"]
    transition_status = transition_decision["transition_status"]
    blocked = transition_action == "block" or transition_status == "blocked"

    step_result = {
        "step_id": transition_decision["step_id"],
        "step_index": current_step_index,
        "status": "blocked" if blocked else "completed",
        "result_ref": transition_decision["source_decision_ref"],
        "updated_at": iso_now(clock),
    }
    state["step_results"] = [*state["step_results"], step_result]

    if blocked:
        state["queue_status"] = "blocked"
        state["current_step_index"] = current_step_index + 1
    else:
        next_index = current_step_index + 1
        state["current_step_index"] = next_index
        if next_index == total_steps:
            state["queue_status"] = "completed"
            state["active_work_item_id"] = None
        else:
            state["queue_status"] = "running"

    now = iso_now(clock)
    state["updated_at"] = now
    state["last_updated"] = now
    return state


def run_queue_once(queue_state: dict, manifest: dict) -> dict:
    """Execute exactly one deterministic, fail-closed queue step iteration."""
    from spectrum_systems.modules.prompt_queue.execution_queue_integration import (
        ExecutionQueueIntegrationError,
        run_queue_step_execution_adapter,
    )
    from spectrum_systems.modules.prompt_queue.post_execution_policy import (
        TransitionDecisionBuildError,
        build_queue_transition_decision,
    )
    from spectrum_systems.modules.prompt_queue.review_parser import ReviewParseError, parse_queue_step_report
    from spectrum_systems.modules.prompt_queue.step_decision import StepDecisionError, build_step_decision

    state, normalized_manifest = _validate_loop_inputs(queue_state, manifest)
    step = _select_next_eligible_step(state, normalized_manifest)

    if step is None:
        if (
            state.get("current_step_index") == state.get("total_steps")
            and all(result.get("status") == "completed" for result in state.get("step_results", []))
        ):
            completed = _clone_queue_state(state)
            completed["queue_status"] = "completed"
            completed["active_work_item_id"] = None
            now = iso_now(utc_now)
            completed["updated_at"] = now
            completed["last_updated"] = now
            return completed
        raise QueueLoopError("next step cannot be determined")

    execution_step, input_refs = _build_step_execution_inputs(state, step)

    try:
        execution_result = run_queue_step_execution_adapter(
            queue_state=state,
            step=execution_step,
            input_refs=input_refs,
        )
    except ExecutionQueueIntegrationError as exc:
        raise QueueLoopError(f"execution failed without valid artifact: {exc}") from exc

    if execution_result.get("execution_status") != "success" and not execution_result.get("output_reference"):
        raise QueueLoopError("execution fails without valid artifact output_reference")

    try:
        findings = parse_queue_step_report(execution_result)
    except ReviewParseError as exc:
        raise QueueLoopError(f"parsing fails: {exc}") from exc

    try:
        step_decision = build_step_decision(findings)
    except StepDecisionError as exc:
        raise QueueLoopError(f"step decision failed closed: {exc}") from exc

    try:
        transition_decision = build_queue_transition_decision(step_decision)
    except TransitionDecisionBuildError as exc:
        raise QueueLoopError(f"transition decision missing or ambiguous: {exc}") from exc

    if not isinstance(transition_decision, dict):
        raise QueueLoopError("transition decision missing")

    allow_warn = bool(normalized_manifest.get("execution_policy", {}).get("allow_warn"))
    action = transition_decision.get("transition_action")
    status = transition_decision.get("transition_status")

    if action == "block" or status == "blocked":
        return apply_transition_to_queue_state(state, transition_decision)

    if action == "continue" and status == "allowed":
        return apply_transition_to_queue_state(state, transition_decision)

    if action == "request_review" and status == "allowed" and allow_warn:
        return apply_transition_to_queue_state(state, transition_decision)

    blocked_transition = dict(transition_decision)
    blocked_transition["transition_action"] = "block"
    blocked_transition["transition_status"] = "blocked"
    reason_codes = list(blocked_transition.get("reason_codes") or [])
    if "unsupported_transition_for_queue_loop" not in reason_codes:
        reason_codes.append("unsupported_transition_for_queue_loop")
    blocked_transition["reason_codes"] = reason_codes
    blocking_reasons = list(blocked_transition.get("blocking_reasons") or [])
    if "unsupported_transition" not in blocking_reasons:
        blocking_reasons.append("unsupported_transition")
    blocked_transition["blocking_reasons"] = blocking_reasons
    return apply_transition_to_queue_state(state, blocked_transition)




def _canonical_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _stable_hash(payload: dict) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _normalize_ref(ref: str) -> str:
    candidate = Path(ref)
    return str(candidate.as_posix()) if candidate.suffix else ref


def _require_existing_artifact_ref(ref: str, field: str) -> Path:
    if not isinstance(ref, str) or not ref.strip():
        raise QueueLoopError(f"{field} missing")
    path = Path(ref)
    if not path.exists() or not path.is_file():
        raise QueueLoopError(f"{field} missing or invalid artifact reference: {ref}")
    return path


def _build_checkpoint_id(
    queue_id: str,
    manifest_ref: str,
    queue_state_ref: str,
    last_completed_step_index: int,
    last_transition_decision_ref: str,
    trace_id: str,
) -> str:
    source = {
        "queue_id": queue_id,
        "manifest_ref": _normalize_ref(manifest_ref),
        "queue_state_ref": _normalize_ref(queue_state_ref),
        "last_completed_step_index": last_completed_step_index,
        "last_transition_decision_ref": _normalize_ref(last_transition_decision_ref),
        "trace_id": trace_id,
    }
    return f"checkpoint-{_stable_hash(source)}"


def _expected_next_step_id(step_index: int) -> str:
    return f"step-{step_index + 1:03d}"


def _extract_transition_from_last_step(queue_state: dict) -> str:
    step_results = queue_state.get("step_results", [])
    if not step_results:
        raise QueueLoopError("checkpoint requires at least one completed step result")
    result_ref = step_results[-1].get("result_ref")
    if not isinstance(result_ref, str) or not result_ref:
        raise QueueLoopError("checkpoint requires last step result_ref")
    return result_ref


def build_queue_resume_checkpoint(queue_state: dict, last_transition: dict) -> dict:
    """Build and validate a deterministic queue resume checkpoint artifact."""
    if not isinstance(last_transition, dict):
        raise QueueLoopError("last_transition must be an object")
    try:
        validate_queue_state(queue_state)
    except ArtifactValidationError as exc:
        raise QueueLoopError(f"invalid queue_state: {exc}") from exc
    normalized_state = dict(queue_state)

    manifest_ref = last_transition.get("manifest_ref")
    queue_state_ref = last_transition.get("queue_state_ref")
    trace_id = last_transition.get("trace_id") or last_transition.get("trace_linkage")
    if not isinstance(manifest_ref, str) or not manifest_ref:
        raise QueueLoopError("checkpoint creation requires manifest_ref")
    if not isinstance(queue_state_ref, str) or not queue_state_ref:
        raise QueueLoopError("checkpoint creation requires queue_state_ref")
    if not isinstance(trace_id, str) or not trace_id:
        raise QueueLoopError("checkpoint creation requires trace_id")

    last_transition_ref = last_transition.get("transition_decision_ref") or _extract_transition_from_last_step(normalized_state)
    last_completed_step_index = int(normalized_state.get("current_step_index", 0)) - 1
    if last_completed_step_index < 0:
        raise QueueLoopError("checkpoint requires at least one successful step")

    checkpoint = {
        "checkpoint_id": _build_checkpoint_id(
            queue_id=normalized_state["queue_id"],
            manifest_ref=manifest_ref,
            queue_state_ref=queue_state_ref,
            last_completed_step_index=last_completed_step_index,
            last_transition_decision_ref=last_transition_ref,
            trace_id=trace_id,
        ),
        "queue_id": normalized_state["queue_id"],
        "manifest_ref": manifest_ref,
        "queue_state_ref": queue_state_ref,
        "last_completed_step_index": last_completed_step_index,
        "last_transition_decision_ref": last_transition_ref,
        "trace_id": trace_id,
        "created_at": last_transition.get("timestamp") or normalized_state.get("last_updated") or normalized_state.get("updated_at"),
    }

    validate_resume_checkpoint(checkpoint)
    return checkpoint


def _validate_checkpoint_integrity(checkpoint: dict) -> tuple[dict, dict, dict]:
    validate_resume_checkpoint(checkpoint)

    expected_id = _build_checkpoint_id(
        queue_id=checkpoint["queue_id"],
        manifest_ref=checkpoint["manifest_ref"],
        queue_state_ref=checkpoint["queue_state_ref"],
        last_completed_step_index=int(checkpoint["last_completed_step_index"]),
        last_transition_decision_ref=checkpoint["last_transition_decision_ref"],
        trace_id=checkpoint["trace_id"],
    )
    if checkpoint["checkpoint_id"] != expected_id:
        raise QueueLoopError("checkpoint integrity mismatch: checkpoint_id is not deterministic")

    state_path = _require_existing_artifact_ref(checkpoint["queue_state_ref"], "queue_state_ref")
    manifest_path = _require_existing_artifact_ref(checkpoint["manifest_ref"], "manifest_ref")
    transition_path = _require_existing_artifact_ref(checkpoint["last_transition_decision_ref"], "last_transition_decision_ref")

    queue_state = read_json_artifact(state_path)
    manifest = read_json_artifact(manifest_path)
    transition = read_json_artifact(transition_path)

    queue_state = _validate_loop_inputs(queue_state, manifest)[0]

    if queue_state.get("queue_id") != checkpoint["queue_id"]:
        raise QueueLoopError("checkpoint integrity mismatch: queue_id differs from queue_state")
    if manifest.get("queue_id") != checkpoint["queue_id"]:
        raise QueueLoopError("checkpoint integrity mismatch: queue_id differs from manifest")
    if transition.get("queue_id") not in {None, checkpoint["queue_id"]}:
        raise QueueLoopError("invalid lineage: transition queue_id mismatch")
    if transition.get("trace_linkage") not in {None, checkpoint["trace_id"]}:
        raise QueueLoopError("invalid lineage: transition trace linkage mismatch")

    expected_result_ref = _extract_transition_from_last_step(queue_state)
    if expected_result_ref != checkpoint["last_transition_decision_ref"]:
        raise QueueLoopError("checkpoint integrity mismatch: last transition ref does not match queue_state")

    return queue_state, manifest, transition


def resume_queue_from_checkpoint(checkpoint: dict) -> dict:
    """Resume queue execution from a validated checkpoint only."""
    queue_state, manifest, _ = _validate_checkpoint_integrity(checkpoint)

    next_state = run_queue_once(deepcopy(queue_state), deepcopy(manifest))
    if next_state.get("queue_id") != checkpoint.get("queue_id"):
        raise QueueLoopError("resume produced inconsistent queue_id")
    if int(next_state.get("current_step_index", 0)) <= int(checkpoint["last_completed_step_index"]):
        raise QueueLoopError("resume did not advance queue progression")
    return next_state


def replay_queue_from_checkpoint(checkpoint: dict) -> dict:
    """Replay queue from checkpoint and emit deterministic parity record."""
    from spectrum_systems.modules.runtime.replay_engine import compare_replay_outputs

    queue_state, manifest, _ = _validate_checkpoint_integrity(checkpoint)

    replayed_state_a = run_queue_once(deepcopy(queue_state), deepcopy(manifest))
    replayed_state_b = run_queue_once(deepcopy(queue_state), deepcopy(manifest))

    replay_step_a = replayed_state_a.get("step_results", [])[-1] if replayed_state_a.get("step_results") else None
    replay_step_b = replayed_state_b.get("step_results", [])[-1] if replayed_state_b.get("step_results") else None
    if replay_step_a is None or replay_step_b is None:
        raise QueueLoopError("non-deterministic replay result: missing replayed step result")

    compared = compare_replay_outputs(
        original_spans=[{"span_id": "queue-transition", "status": replay_step_a.get("status")}],
        replay_steps=[{"original_span_id": "queue-transition", "status": replay_step_b.get("status")}],
    )
    transition_match = bool(compared.get("matched") is True)
    decision_match = replay_step_a.get("result_ref") == replay_step_b.get("result_ref")

    replay_state_projection_a = {
        "queue_status": replayed_state_a.get("queue_status"),
        "current_step_index": replayed_state_a.get("current_step_index"),
        "last_result_ref": replay_step_a.get("result_ref"),
    }
    replay_state_projection_b = {
        "queue_status": replayed_state_b.get("queue_status"),
        "current_step_index": replayed_state_b.get("current_step_index"),
        "last_result_ref": replay_step_b.get("result_ref"),
    }
    state_match = _stable_hash(replay_state_projection_a) == _stable_hash(replay_state_projection_b)

    parity_match = transition_match and decision_match and state_match
    mismatch_details = []
    if not decision_match:
        mismatch_details.append("decision_ref divergence")
    if not transition_match:
        mismatch_details.append("transition_status divergence")
    if not state_match:
        mismatch_details.append("state projection divergence")

    payload_source = {
        "queue_id": checkpoint["queue_id"],
        "checkpoint_id": checkpoint["checkpoint_id"],
        "last_transition_decision_ref": checkpoint["last_transition_decision_ref"],
        "expected_step": _expected_next_step_id(int(checkpoint["last_completed_step_index"]) + 1),
    }

    replay_record = {
        "replay_id": f"queue-replay-{_stable_hash(payload_source)}",
        "queue_id": checkpoint["queue_id"],
        "checkpoint_ref": checkpoint["queue_state_ref"],
        "input_refs": [
            checkpoint["queue_state_ref"],
            checkpoint["manifest_ref"],
            checkpoint["last_transition_decision_ref"],
        ],
        "replay_result_summary": {
            "replayed_step_id": replay_step_a.get(
                "step_id",
                _expected_next_step_id(int(checkpoint["last_completed_step_index"]) + 1),
            ),
            "decision_match": decision_match,
            "state_match": state_match,
            "transition_match": transition_match,
        },
        "parity_status": "match" if parity_match else "mismatch",
        "mismatch_summary": None if parity_match else "; ".join(mismatch_details),
        "trace_id": checkpoint["trace_id"],
        "timestamp": checkpoint["created_at"],
    }

    validate_replay_record(replay_record)
    if replay_record["parity_status"] == "mismatch" and not replay_record.get("mismatch_summary"):
        raise QueueLoopError("replay mismatch without explicit report")

    return replay_record

def transition_work_item(
    work_item: dict,
    to_status: str,
    *,
    clock: Clock = utc_now,
) -> dict:
    from_status = work_item["status"]
    allowed = _ALLOWED_TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        raise IllegalTransitionError(
            f"Illegal transition from '{from_status}' to '{to_status}'. Allowed={sorted(allowed)}"
        )
    updated = dict(work_item)
    updated["status"] = to_status
    updated["updated_at"] = iso_now(clock)
    return updated
