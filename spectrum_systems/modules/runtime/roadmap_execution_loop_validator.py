"""Deterministic end-to-end governed single-batch roadmap execution loop validation (RDX-005)."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator, FormatChecker

from spectrum_systems.contracts import load_schema
from spectrum_systems.modules.runtime.roadmap_authorizer import authorize_selected_batch
from spectrum_systems.modules.runtime.roadmap_executor import execute_authorized_batch
from spectrum_systems.modules.runtime.roadmap_selector import build_roadmap_selection_result
from spectrum_systems.modules.runtime.roadmap_stop_reasons import (
    STOP_REASON_INVALID_PROGRESS_STATE,
    STOP_REASON_LOOP_VALIDATION_FAILED,
    STOP_REASON_REPLAY_NOT_READY,
)


class RoadmapExecutionLoopValidationError(ValueError):
    """Raised when the roadmap execution loop cannot be validated safely."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _canonical_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _validation_id(seed: dict[str, Any]) -> str:
    return f"RLV-{_canonical_hash(seed)[:12].upper()}"


def _validate_schema(instance: dict[str, Any], schema_name: str, *, label: str) -> None:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise RoadmapExecutionLoopValidationError(f"{label} failed schema validation ({schema_name}): {details}")


def _status_by_batch_id(roadmap_artifact: dict[str, Any]) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for row in roadmap_artifact.get("batches", []):
        if isinstance(row, dict) and isinstance(row.get("batch_id"), str) and isinstance(row.get("status"), str):
            statuses[row["batch_id"]] = row["status"]
    return statuses


def _changed_batches(before: dict[str, str], after: dict[str, str]) -> list[str]:
    keys = sorted(set(before) | set(after))
    return [key for key in keys if before.get(key) != after.get(key)]


def _resolve_selected_batch_status(roadmap_artifact: dict[str, Any], batch_id: str | None) -> str:
    if batch_id is None:
        return "none"
    for batch in roadmap_artifact.get("batches", []):
        if isinstance(batch, dict) and batch.get("batch_id") == batch_id:
            status = batch.get("status")
            if isinstance(status, str):
                return status
            return "none"
    return "none"


def _is_deterministic(
    *,
    evaluated_at: str | None,
    validated_at: str | None,
    executed_at: str | None,
    execution_expected: bool,
) -> bool:
    if not evaluated_at or not validated_at:
        return False
    if execution_expected and not executed_at:
        return False
    return True


def _build_source_refs(execution_occurred: bool, source_refs: dict[str, str | None] | None) -> dict[str, str | None]:
    merged = {
        "roadmap_artifact": "roadmap_artifact:inline",
        "selection_result": "roadmap_selection_result:inline",
        "authorization_result": "roadmap_execution_authorization:inline",
        "pqx_result": "pqx_result:inline" if execution_occurred else None,
        "progress_update": "roadmap_progress_update:inline" if execution_occurred else None,
    }
    if source_refs:
        for key in merged:
            if key in source_refs:
                value = source_refs[key]
                if isinstance(value, str) and not value.strip():
                    merged[key] = None
                else:
                    merged[key] = value
    return merged


def validate_single_batch_execution_loop(
    roadmap_artifact: dict[str, Any],
    selection_signals: dict[str, Any],
    authorization_signals: dict[str, Any],
    *,
    pqx_state_path: Path,
    pqx_runs_root: Path,
    evaluated_at: str | None = None,
    executed_at: str | None = None,
    validated_at: str | None = None,
    source_refs: dict[str, str | None] | None = None,
    pqx_execute_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate one governed roadmap loop: selection -> authorization -> (optional) execution -> progress consistency."""
    _validate_schema(roadmap_artifact, "roadmap_artifact", label="roadmap_artifact")

    reason_codes: set[str] = set()
    blocking_conditions: set[str] = set()

    original_roadmap = copy.deepcopy(roadmap_artifact)
    selection_result = build_roadmap_selection_result(roadmap_artifact, selection_signals, evaluated_at=evaluated_at)
    authorization_result = authorize_selected_batch(
        roadmap_artifact,
        selection_result,
        authorization_signals,
        evaluated_at=evaluated_at,
    )

    selected_batch_id = selection_result.get("selected_batch_id")
    authorized_batch_id = authorization_result.get("selected_batch_id")
    control_decision = str(authorization_result["control_decision"])
    execution_allowed = bool(authorization_result["authorized_to_run"])
    execution_occurred = False
    progress_update: dict[str, Any] | None = None
    roadmap_after = copy.deepcopy(roadmap_artifact)

    if selected_batch_id != authorized_batch_id:
        reason_codes.add("SELECTION_AUTHORIZATION_MISMATCH")
        reason_codes.add("INCONSISTENT_BATCH_IDENTITY")
        blocking_conditions.add("selection_result.selected_batch_id != authorization.selected_batch_id")

    if execution_allowed and isinstance(selected_batch_id, str):
        try:
            execution_payload = execute_authorized_batch(
                roadmap_artifact,
                selection_result,
                authorization_result,
                pqx_state_path=pqx_state_path,
                pqx_runs_root=pqx_runs_root,
                executed_at=executed_at,
                pqx_execute_fn=pqx_execute_fn,
            )
        except Exception as exc:  # fail-closed at boundary seam
            reason_codes.add("AUTHORIZATION_EXECUTION_MISMATCH")
            blocking_conditions.add(f"execution seam failed closed: {exc}")
        else:
            execution_occurred = bool(execution_payload.get("pqx_called"))
            roadmap_after = execution_payload["roadmap"]
            progress_update = execution_payload["progress_update"]
    elif execution_allowed:
        reason_codes.add("AUTHORIZATION_EXECUTION_MISMATCH")
        blocking_conditions.add("authorization allowed execution but selected_batch_id is null")

    if (control_decision in {"freeze", "block"}) and execution_occurred:
        reason_codes.add("AUTHORIZATION_EXECUTION_MISMATCH")
        blocking_conditions.add("execution occurred for non-authorized control decision")

    if progress_update is not None and not execution_occurred:
        reason_codes.add("PROGRESS_WITHOUT_EXECUTION")
        blocking_conditions.add("progress update exists while execution did not occur")

    if execution_occurred and progress_update is None:
        reason_codes.add("PROGRESS_WITHOUT_EXECUTION")
        blocking_conditions.add("execution occurred without progress update")

    if progress_update is not None:
        progress_selected = progress_update.get("selected_batch_id")
        if progress_selected != selected_batch_id:
            reason_codes.add("INCONSISTENT_BATCH_IDENTITY")
            blocking_conditions.add("progress_update.selected_batch_id mismatch")

        execution_status = progress_update.get("execution_status")
        new_status = progress_update.get("new_batch_status")
        expected_status = "completed" if execution_status == "succeeded" else "blocked"
        if execution_status in {"succeeded", "blocked", "failed"} and new_status != expected_status:
            reason_codes.add("ROADMAP_STATUS_TRANSITION_MISMATCH")
            blocking_conditions.add("progress update status transition does not match execution status")

    before_status = _status_by_batch_id(original_roadmap)
    after_status = _status_by_batch_id(roadmap_after)
    changed = _changed_batches(before_status, after_status)
    if execution_occurred:
        if not isinstance(selected_batch_id, str):
            reason_codes.add("INCONSISTENT_BATCH_IDENTITY")
            blocking_conditions.add("selected batch id missing despite execution")
        else:
            allowed_changed = {selected_batch_id}
            if set(changed) - allowed_changed:
                reason_codes.add("MULTI_BATCH_EXECUTION_DETECTED")
                blocking_conditions.add(
                    "roadmap status changed for non-selected batches: "
                    + ", ".join(sorted(set(changed) - allowed_changed))
                )
    elif changed:
        reason_codes.add("AUTHORIZATION_EXECUTION_MISMATCH")
        blocking_conditions.add("roadmap mutated despite no execution")

    refs = _build_source_refs(execution_occurred, source_refs)
    replay_missing: list[str] = []
    required_replay_keys = ["roadmap_artifact", "selection_result", "authorization_result"]
    if execution_occurred:
        required_replay_keys.extend(["pqx_result", "progress_update"])
    for key in required_replay_keys:
        value = refs.get(key)
        if value is None:
            replay_missing.append(key)
        elif isinstance(value, str) and not value.strip():
            replay_missing.append(key)
    if replay_missing:
        reason_codes.add("REPLAY_CHAIN_INCOMPLETE")
        blocking_conditions.add("missing replay-critical refs: " + ", ".join(sorted(replay_missing)))

    deterministic = _is_deterministic(
        evaluated_at=evaluated_at,
        validated_at=validated_at,
        executed_at=executed_at,
        execution_expected=execution_occurred,
    )
    if not deterministic:
        reason_codes.add("NON_DETERMINISTIC_LOOP_RESULT")
        blocking_conditions.add("deterministic timestamps (evaluated_at/validated_at/executed_at) are required")

    if not reason_codes:
        if execution_occurred:
            reason_codes.add("LOOP_VALIDATION_PASSED")
        else:
            reason_codes.add("LOOP_VALIDATION_DENIED_PATH")

    stage_consistency = "inconsistent" if reason_codes.intersection(
        {
            "SELECTION_AUTHORIZATION_MISMATCH",
            "AUTHORIZATION_EXECUTION_MISMATCH",
            "PROGRESS_WITHOUT_EXECUTION",
            "INCONSISTENT_BATCH_IDENTITY",
            "ROADMAP_STATUS_TRANSITION_MISMATCH",
            "MULTI_BATCH_EXECUTION_DETECTED",
        }
    ) else "consistent"

    replay_ready = "REPLAY_CHAIN_INCOMPLETE" not in reason_codes
    determinism_status = "deterministic" if deterministic else "non_deterministic"
    loop_status = "passed" if stage_consistency == "consistent" and replay_ready and deterministic else "failed_closed"
    stop_reason: str | None = None
    if loop_status != "passed":
        if not replay_ready:
            stop_reason = STOP_REASON_REPLAY_NOT_READY
        elif "PROGRESS_WITHOUT_EXECUTION" in reason_codes:
            stop_reason = STOP_REASON_INVALID_PROGRESS_STATE
        else:
            stop_reason = STOP_REASON_LOOP_VALIDATION_FAILED

    selected_batch_status = _resolve_selected_batch_status(roadmap_after, selected_batch_id if isinstance(selected_batch_id, str) else None)

    timestamp = validated_at or _utc_now()
    input_hash = _canonical_hash(
        {
            "roadmap_artifact": roadmap_artifact,
            "selection_signals": selection_signals,
            "authorization_signals": authorization_signals,
            "selection_result": selection_result,
            "authorization_result": authorization_result,
            "progress_update": progress_update,
            "execution_occurred": execution_occurred,
            "source_refs": refs,
        }
    )

    validation_seed = {
        "roadmap_id": roadmap_artifact["roadmap_id"],
        "selected_batch_id": selected_batch_id,
        "authorization_id": authorization_result["authorization_id"],
        "progress_update_id": progress_update.get("progress_update_id") if progress_update else None,
        "loop_status": loop_status,
        "input_hash": input_hash,
        "validated_at": timestamp,
    }

    validation_artifact = {
        "validation_id": _validation_id(validation_seed),
        "schema_version": "1.1.0",
        "roadmap_id": roadmap_artifact["roadmap_id"],
        "selected_batch_id": selected_batch_id if isinstance(selected_batch_id, str) else None,
        "authorization_id": authorization_result["authorization_id"],
        "progress_update_id": progress_update.get("progress_update_id") if progress_update else None,
        "loop_status": loop_status,
        "selected_batch_status": selected_batch_status,
        "control_decision": control_decision,
        "execution_occurred": execution_occurred,
        "stage_consistency": stage_consistency,
        "determinism_status": determinism_status,
        "replay_ready": replay_ready,
        "stop_reason": stop_reason,
        "stop_reason_codes": [stop_reason] if isinstance(stop_reason, str) else [],
        "reason_codes": sorted(reason_codes),
        "blocking_conditions": sorted(blocking_conditions),
        "validated_at": timestamp,
        "input_hash": input_hash,
        "trace_id": authorization_result["trace_id"],
        "source_refs": refs,
    }
    _validate_schema(validation_artifact, "roadmap_execution_loop_validation", label="roadmap_execution_loop_validation")

    return {
        "selection_result": selection_result,
        "authorization_result": authorization_result,
        "progress_update": progress_update,
        "roadmap": roadmap_after,
        "loop_validation": validation_artifact,
    }


__all__ = [
    "RoadmapExecutionLoopValidationError",
    "validate_single_batch_execution_loop",
]
