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
    STOP_REASON_DIMINISHING_RETURNS,
    STOP_REASON_EXECUTION_BLOCKED,
    STOP_REASON_EXECUTION_FAILED,
    STOP_REASON_HARD_GATE_STOP,
    STOP_REASON_INVALID_PROGRESS_STATE,
    STOP_REASON_INVALID_ROADMAP_STATE,
    STOP_REASON_LOOP_VALIDATION_FAILED,
    STOP_REASON_MAX_BATCHES_REACHED,
    STOP_REASON_NO_ELIGIBLE_BATCH,
    STOP_REASON_REPEATED_FAILURE_PATTERN,
    STOP_REASON_REPLAY_NOT_READY,
    STOP_REASON_RISK_ACCUMULATION_EXCEEDED,
    STOP_REASON_UNRESOLVED_BLOCKER_PERSISTS,
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
    max_batches_raw = raw.get("max_batches_per_run", 2)

    mode = "static"
    static_cap: int | None = None
    adaptive_policy: dict[str, Any] = {}

    if isinstance(max_batches_raw, int):
        if max_batches_raw < 1:
            raise RoadmapMultiBatchExecutionError("execution_policy.max_batches_per_run must be an integer >= 1")
        static_cap = max_batches_raw
    elif isinstance(max_batches_raw, dict):
        mode = "adaptive"
        adaptive_policy = dict(max_batches_raw)
    else:
        raise RoadmapMultiBatchExecutionError("execution_policy.max_batches_per_run must be an integer or object")

    allow_warn_execution = bool(raw.get("allow_warn_execution", True))
    stop_on_warn = bool(raw.get("stop_on_warn", False))
    stop_on_hard_gate = bool(raw.get("stop_on_hard_gate", True))

    if mode == "adaptive":
        min_cap = int(adaptive_policy.get("min_cap", 1))
        max_cap = int(adaptive_policy.get("max_cap", 4))
        if min_cap < 1 or max_cap < min_cap:
            raise RoadmapMultiBatchExecutionError("adaptive min/max cap must satisfy 1 <= min_cap <= max_cap")
        risk_caps = adaptive_policy.get("risk_caps") or {"low": 4, "medium": 2, "high": 1}
        if not isinstance(risk_caps, dict):
            raise RoadmapMultiBatchExecutionError("adaptive risk_caps must be an object")

        normalized_risk_caps = {
            "low": int(risk_caps.get("low", 4)),
            "medium": int(risk_caps.get("medium", 2)),
            "high": int(risk_caps.get("high", 1)),
        }
        for value in normalized_risk_caps.values():
            if value < 1:
                raise RoadmapMultiBatchExecutionError("adaptive risk caps must be >= 1")

        phase_caps_raw = adaptive_policy.get("program_phase_caps") or {
            "discovery": 2,
            "build": 3,
            "stabilization": 2,
            "containment": 1,
        }
        if not isinstance(phase_caps_raw, dict):
            raise RoadmapMultiBatchExecutionError("adaptive program_phase_caps must be an object")
        program_phase_caps = {str(key): int(value) for key, value in phase_caps_raw.items()}

        adaptive_policy = {
            "min_cap": min_cap,
            "max_cap": max_cap,
            "risk_caps": normalized_risk_caps,
            "program_phase_caps": program_phase_caps,
            "recent_failure_penalty": int(adaptive_policy.get("recent_failure_penalty", 1)),
            "warning_cap": int(adaptive_policy.get("warning_cap", 2)),
            "risk_accumulation_stop_threshold": int(adaptive_policy.get("risk_accumulation_stop_threshold", 6)),
        }
    else:
        adaptive_policy = {
            "min_cap": static_cap,
            "max_cap": static_cap,
            "risk_caps": {},
            "program_phase_caps": {},
            "recent_failure_penalty": 0,
            "warning_cap": static_cap,
            "risk_accumulation_stop_threshold": 6,
        }

    return {
        "mode": mode,
        "max_batches_per_run": static_cap if static_cap is not None else adaptive_policy["max_cap"],
        "adaptive_policy": adaptive_policy,
        "allow_warn_execution": allow_warn_execution,
        "stop_on_warn": stop_on_warn,
        "stop_on_hard_gate": stop_on_hard_gate,
    }


def _resolve_batch(roadmap_artifact: dict[str, Any], batch_id: str) -> dict[str, Any] | None:
    for batch in roadmap_artifact.get("batches", []):
        if isinstance(batch, dict) and batch.get("batch_id") == batch_id:
            return batch
    return None


def _resolve_risk_level(selection_signals: dict[str, Any], authorization_signals: dict[str, Any]) -> str:
    direct = str(selection_signals.get("risk_level") or authorization_signals.get("risk_level") or "").strip().lower()
    if direct in {"low", "medium", "high"}:
        return direct
    risk_signals = selection_signals.get("context_risk_signals")
    if isinstance(risk_signals, list) and len(risk_signals) >= 2:
        return "high"
    if isinstance(risk_signals, list) and len(risk_signals) == 1:
        return "medium"
    return "medium"


def _resolve_program_phase(selection_signals: dict[str, Any]) -> str:
    phase = str(selection_signals.get("program_phase") or "build").strip().lower()
    return phase or "build"


def _resolve_max_batches_for_state(
    policy: dict[str, Any],
    selection_signals: dict[str, Any],
    authorization_signals: dict[str, Any],
    continuation_state: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    if policy["mode"] == "static":
        resolved = int(policy["max_batches_per_run"])
        return resolved, {"mode": "static", "resolved_from": ["static_cap"]}

    adaptive = policy["adaptive_policy"]
    risk_level = _resolve_risk_level(selection_signals, authorization_signals)
    phase = _resolve_program_phase(selection_signals)

    resolved = int(adaptive["risk_caps"][risk_level])
    reasons: list[str] = [f"risk:{risk_level}"]

    phase_cap = adaptive["program_phase_caps"].get(phase)
    if isinstance(phase_cap, int):
        resolved = min(resolved, phase_cap)
        reasons.append(f"phase:{phase}")

    recent_failures = int(continuation_state.get("recent_failures", 0))
    if recent_failures > 0:
        resolved = max(adaptive["min_cap"], resolved - (adaptive["recent_failure_penalty"] * recent_failures))
        reasons.append(f"recent_failures:{recent_failures}")

    warning_states = authorization_signals.get("warning_states")
    if isinstance(warning_states, list) and warning_states:
        resolved = min(resolved, int(adaptive["warning_cap"]))
        reasons.append("warnings_present")

    if bool(authorization_signals.get("control_block_condition")) or bool(authorization_signals.get("control_freeze_condition")):
        resolved = 1
        reasons.append("control_condition")

    resolved = max(adaptive["min_cap"], min(adaptive["max_cap"], resolved))
    return resolved, {
        "mode": "adaptive",
        "risk_level": risk_level,
        "program_phase": phase,
        "recent_failures": recent_failures,
        "resolved_from": reasons,
    }


def should_continue_execution(
    last_batch_result: dict[str, Any] | None,
    control_decision: str,
    context_risk_signals: dict[str, Any],
    program_alignment: dict[str, Any],
    replay_integrity: str,
    continuation_state: dict[str, Any],
) -> dict[str, Any]:
    """Deterministic stop/continue policy for bounded multi-batch execution."""
    if last_batch_result is None:
        return {"continue": True, "reason_code": "continue_initial"}

    if control_decision in {"freeze", "block"}:
        return {"continue": False, "reason_code": f"control_decision_{control_decision}"}

    if replay_integrity != "ready":
        return {"continue": False, "reason_code": STOP_REASON_REPLAY_NOT_READY}

    if int(continuation_state.get("consecutive_non_progress", 0)) >= 2:
        return {"continue": False, "reason_code": STOP_REASON_DIMINISHING_RETURNS}

    if int(continuation_state.get("repeated_failure_reason_count", 0)) >= 2:
        return {"continue": False, "reason_code": STOP_REASON_REPEATED_FAILURE_PATTERN}

    if int(continuation_state.get("unresolved_blocker_streak", 0)) >= 2:
        return {"continue": False, "reason_code": STOP_REASON_UNRESOLVED_BLOCKER_PERSISTS}

    risk_accumulation = int(continuation_state.get("risk_accumulation", 0))
    risk_threshold = int(continuation_state.get("risk_accumulation_stop_threshold", 6))
    if risk_accumulation >= risk_threshold:
        return {"continue": False, "reason_code": STOP_REASON_RISK_ACCUMULATION_EXCEEDED}

    risk_level = str(context_risk_signals.get("risk_level") or "medium")
    if risk_level == "high" and not bool(program_alignment.get("safety_critical", True)):
        return {"continue": False, "reason_code": STOP_REASON_RISK_ACCUMULATION_EXCEEDED}

    return {"continue": True, "reason_code": "continue_safe"}


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
    """Execute bounded roadmap batches with deterministic adaptive continuation controls."""
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

    continuation_decisions: list[dict[str, Any]] = []
    chain_context: list[dict[str, Any]] = []

    continuation_state = {
        "recent_failures": 0,
        "consecutive_non_progress": 0,
        "repeated_failure_reason_count": 0,
        "last_failure_reason": None,
        "unresolved_blocker_streak": 0,
        "risk_accumulation": 0,
        "risk_accumulation_stop_threshold": int(policy["adaptive_policy"]["risk_accumulation_stop_threshold"]),
    }

    current_roadmap = copy.deepcopy(roadmap_artifact)
    last_batch_result: dict[str, Any] | None = None
    resolved_max_batches_per_run, adaptive_factors = _resolve_max_batches_for_state(
        policy,
        selection_signals,
        authorization_signals,
        continuation_state,
    )

    while True:
        resolved_max_batches_per_run, adaptive_factors = _resolve_max_batches_for_state(
            policy,
            selection_signals,
            authorization_signals,
            continuation_state,
        )
        if len(attempted_batch_ids) >= resolved_max_batches_per_run:
            stop_reason = STOP_REASON_MAX_BATCHES_REACHED
            stop_reason_codes = [STOP_REASON_MAX_BATCHES_REACHED]
            break

        continuation_decision = should_continue_execution(
            last_batch_result,
            str((last_batch_result or {}).get("control_decision") or "allow"),
            {"risk_level": _resolve_risk_level(selection_signals, authorization_signals)},
            {"safety_critical": True, "program_phase": _resolve_program_phase(selection_signals)},
            str((last_batch_result or {}).get("replay_integrity") or "ready"),
            continuation_state,
        )
        continuation_decisions.append(
            {
                "step": len(continuation_decisions) + 1,
                "decision": "continue" if continuation_decision["continue"] else "stop",
                "reason_code": continuation_decision["reason_code"],
            }
        )
        if not continuation_decision["continue"]:
            stop_reason = continuation_decision["reason_code"]
            stop_reason_codes = [continuation_decision["reason_code"]]
            break

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
        except RoadmapExecutionLoopValidationError:
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

        control_decision = str(authorization.get("control_decision") or "allow")
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
        failure_reason_for_tracking: str | None = None
        if execution_status == "succeeded":
            if not isinstance(selected_batch_id, str):
                stop_reason = STOP_REASON_INVALID_ROADMAP_STATE
                stop_reason_codes = [STOP_REASON_INVALID_ROADMAP_STATE]
                break
            completed_batch_ids.append(selected_batch_id)
            continuation_state["recent_failures"] = 0
            continuation_state["consecutive_non_progress"] = 0
            continuation_state["unresolved_blocker_streak"] = 0
        elif execution_status == "blocked":
            blocked_batch_id = selected_batch_id if isinstance(selected_batch_id, str) else None
            failure_reason_for_tracking = str(progress.get("stop_reason") or STOP_REASON_EXECUTION_BLOCKED)
            stop_reason = failure_reason_for_tracking
            stop_reason_codes = [stop_reason]
            continuation_state["recent_failures"] = int(continuation_state["recent_failures"]) + 1
            continuation_state["consecutive_non_progress"] = int(continuation_state["consecutive_non_progress"]) + 1
            continuation_state["unresolved_blocker_streak"] = int(continuation_state["unresolved_blocker_streak"]) + 1
            break
        elif execution_status in {"failed", "not_executed"}:
            if execution_status == "not_executed":
                failure_reason_for_tracking = str(progress.get("stop_reason") or STOP_REASON_AUTHORIZATION_BLOCK)
            else:
                failure_reason_for_tracking = str(progress.get("stop_reason") or STOP_REASON_EXECUTION_FAILED)
            stop_reason = failure_reason_for_tracking
            stop_reason_codes = [stop_reason]
            continuation_state["recent_failures"] = int(continuation_state["recent_failures"]) + 1
            continuation_state["consecutive_non_progress"] = int(continuation_state["consecutive_non_progress"]) + 1
            break
        else:
            stop_reason = STOP_REASON_INVALID_PROGRESS_STATE
            stop_reason_codes = [STOP_REASON_INVALID_PROGRESS_STATE]
            break

        if failure_reason_for_tracking is not None:
            if continuation_state.get("last_failure_reason") == failure_reason_for_tracking:
                continuation_state["repeated_failure_reason_count"] = int(
                    continuation_state.get("repeated_failure_reason_count", 0)
                ) + 1
            else:
                continuation_state["repeated_failure_reason_count"] = 1
            continuation_state["last_failure_reason"] = failure_reason_for_tracking
        else:
            continuation_state["last_failure_reason"] = None
            continuation_state["repeated_failure_reason_count"] = 0

        risk_level = _resolve_risk_level(selection_signals, authorization_signals)
        continuation_state["risk_accumulation"] = int(continuation_state["risk_accumulation"]) + {
            "low": 1,
            "medium": 2,
            "high": 3,
        }[risk_level]

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

        chain_context.append(
            {
                "batch_id": selected_batch_id,
                "roadmap_hash": _canonical_hash(updated_roadmap),
                "progress_update_id": progress.get("progress_update_id"),
                "failure_learning": (progress.get("stop_reason") if execution_status != "succeeded" else None),
            }
        )

        last_batch_result = {
            "control_decision": control_decision,
            "replay_integrity": "ready" if loop_validation.get("replay_ready") is True else "not_ready",
            "execution_status": execution_status,
        }
        current_roadmap = updated_roadmap

    early_stop = stop_reason != STOP_REASON_MAX_BATCHES_REACHED
    useful_batches = len(completed_batch_ids)
    attempted = len(attempted_batch_ids)
    avg_progress = round(useful_batches / attempted, 4) if attempted else 0.0

    seed = {
        "roadmap_id": roadmap_artifact["roadmap_id"],
        "attempted_batch_ids": attempted_batch_ids,
        "completed_batch_ids": completed_batch_ids,
        "stop_reason": stop_reason,
        "max_batches_per_run": policy["max_batches_per_run"],
        "resolved_max_batches_per_run": resolved_max_batches_per_run,
        "input_hash": input_hash,
        "executed_at": timestamp,
    }

    result = {
        "run_id": _run_id(seed),
        "schema_version": "1.2.0",
        "roadmap_id": roadmap_artifact["roadmap_id"],
        "attempted_batch_ids": attempted_batch_ids,
        "completed_batch_ids": completed_batch_ids,
        "blocked_batch_id": blocked_batch_id,
        "frozen_batch_id": frozen_batch_id,
        "stop_reason": stop_reason,
        "stop_reason_codes": stop_reason_codes,
        "max_batches_per_run": policy["max_batches_per_run"],
        "resolved_max_batches_per_run": resolved_max_batches_per_run,
        "batches_executed_count": useful_batches,
        "final_roadmap_status_ref": f"roadmap_artifact:inline:{current_roadmap['roadmap_id']}",
        "loop_validation_refs": loop_validation_refs,
        "progress_update_refs": progress_update_refs,
        "authorization_refs": authorization_refs,
        "continuation_decision_sequence": continuation_decisions,
        "execution_efficiency_report": {
            "batches_executed_per_run": attempted,
            "useful_batches": useful_batches,
            "early_stops": 1 if early_stop else 0,
            "average_progress_per_run": avg_progress,
            "chain_context_refs": [entry["roadmap_hash"] for entry in chain_context],
            "adaptive_factors": adaptive_factors,
        },
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
    "should_continue_execution",
]
