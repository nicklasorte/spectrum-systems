"""Deterministic fix execution + reinsertion helpers for governed PQX bundle orchestration."""

from __future__ import annotations

from copy import deepcopy

from spectrum_systems.contracts import validate_artifact


class PQXFixExecutionError(ValueError):
    """Raised when fix loop operations violate fail-closed deterministic semantics."""


_ALLOWED_ACTION_TYPES = {"patch", "add", "replace"}
_ALLOWED_TARGETS = {"module", "schema", "test", "runtime"}
_ALLOWED_SEVERITIES = {"critical", "high", "medium", "low"}


def load_pending_fixes(bundle_state: dict) -> list[dict]:
    pending = bundle_state.get("pending_fix_ids", [])
    if not isinstance(pending, list):
        raise PQXFixExecutionError("pending_fix_ids must be a list")
    open_fixes = [fix for fix in pending if isinstance(fix, dict) and fix.get("status") in {"open", "planned", "in_progress"}]
    return sorted(open_fixes, key=lambda fix: (fix.get("priority", "P9"), fix.get("fix_id", "")))


def normalize_fix_into_step(fix: dict) -> dict:
    if not isinstance(fix, dict):
        raise PQXFixExecutionError("fix must be an object")

    fix_id = fix.get("fix_id")
    if not isinstance(fix_id, str) or not fix_id:
        raise PQXFixExecutionError("fix missing fix_id")

    affected = fix.get("affected_step_ids")
    if not isinstance(affected, list) or not affected or not isinstance(affected[0], str) or not affected[0]:
        raise PQXFixExecutionError(f"fix '{fix_id}' must include affected_step_ids[0]")

    severity = fix.get("severity")
    if severity not in _ALLOWED_SEVERITIES:
        raise PQXFixExecutionError(f"fix '{fix_id}' has unsupported severity: {severity}")

    notes = str(fix.get("notes") or "").lower()
    if "replace" in notes:
        action_type = "replace"
    elif "add" in notes:
        action_type = "add"
    else:
        action_type = "patch"

    target = "runtime"
    for candidate in _ALLOWED_TARGETS:
        if candidate in notes:
            target = candidate
            break

    return {
        "fix_step_id": f"fix-step:{fix_id}",
        "fix_id": fix_id,
        "source_step_id": affected[0],
        "severity": severity,
        "action_type": action_type,
        "target": target,
        "trace_id": fix.get("created_from_run_id"),
        "run_id": fix.get("created_from_run_id"),
        "lineage_fix_ref": fix_id,
    }


def validate_fix_step(fix_step: dict, roadmap: list[str]) -> None:
    required = {"fix_id", "source_step_id", "severity", "action_type", "target"}
    missing = sorted(required - set(fix_step))
    if missing:
        raise PQXFixExecutionError(f"malformed fix step missing fields: {missing}")

    if fix_step["action_type"] not in _ALLOWED_ACTION_TYPES:
        raise PQXFixExecutionError(f"unsupported fix action_type: {fix_step['action_type']}")
    if fix_step["target"] not in _ALLOWED_TARGETS:
        raise PQXFixExecutionError(f"unsupported fix target: {fix_step['target']}")
    if fix_step["severity"] not in _ALLOWED_SEVERITIES:
        raise PQXFixExecutionError(f"unsupported fix severity: {fix_step['severity']}")

    if not isinstance(roadmap, list) or not roadmap:
        raise PQXFixExecutionError("roadmap must be a non-empty ordered list")

    source_step_id = fix_step["source_step_id"]
    if source_step_id not in roadmap:
        raise PQXFixExecutionError(
            f"fix '{fix_step['fix_id']}' references missing step/module: {source_step_id}"
        )

    if fix_step["fix_step_id"] in roadmap:
        raise PQXFixExecutionError(
            f"fix '{fix_step['fix_id']}' conflicts with existing roadmap step id: {fix_step['fix_step_id']}"
        )


def determine_fix_insertion_point(fix_step: dict, roadmap: list[str]) -> dict:
    source_step_id = fix_step["source_step_id"]
    source_index = roadmap.index(source_step_id)
    if fix_step["action_type"] == "replace":
        insertion_index = source_index
        mode = "before_source"
    else:
        insertion_index = source_index + 1
        mode = "patch_after_source"

    return {
        "mode": mode,
        "anchor_step_id": source_step_id,
        "insert_before_step_id": roadmap[insertion_index] if insertion_index < len(roadmap) else None,
        "ordered_index": insertion_index,
    }


def execute_fix_step(fix_step: dict, sequence_runner) -> dict:
    result = sequence_runner(fix_step)
    if not isinstance(result, dict):
        raise PQXFixExecutionError("fix execution runner returned non-object result")

    status = result.get("execution_status")
    if status not in {"complete", "blocked", "failed"}:
        raise PQXFixExecutionError("fix execution runner must return execution_status in {complete, blocked, failed}")

    artifacts = result.get("artifacts", [])
    if not isinstance(artifacts, list) or any(not isinstance(ref, str) or not ref for ref in artifacts):
        raise PQXFixExecutionError("fix execution artifacts must be a list of non-empty strings")

    validation_result = result.get("validation_result")
    if not isinstance(validation_result, str) or not validation_result:
        raise PQXFixExecutionError("fix execution must include non-empty validation_result")

    return {
        "fix_step": deepcopy(fix_step),
        "execution_status": status,
        "artifacts": list(dict.fromkeys(artifacts)),
        "validation_result": validation_result,
        "error": result.get("error"),
    }


def record_fix_result(bundle_state: dict, fix_step: dict, result: dict) -> dict:
    insertion = determine_fix_insertion_point(fix_step, _roadmap_from_state(bundle_state))
    record = {
        "schema_version": "1.0.0",
        "fix_id": fix_step["fix_id"],
        "source_step_id": fix_step["source_step_id"],
        "execution_status": result["execution_status"],
        "artifacts": result["artifacts"],
        "validation_result": result["validation_result"],
        "insertion_point": insertion,
        "trace_id": _required_identity(fix_step.get("trace_id"), "trace_id"),
        "run_id": _required_identity(fix_step.get("run_id"), "run_id"),
    }
    try:
        validate_artifact(record, "pqx_fix_execution_record")
    except Exception as exc:
        raise PQXFixExecutionError(f"invalid pqx_fix_execution_record artifact: {exc}") from exc
    return record


def update_bundle_state_with_fix(bundle_state: dict, fix_result: dict) -> dict:
    updated = deepcopy(bundle_state)
    fix_id = fix_result["fix_id"]
    status = fix_result["execution_status"]

    found = False
    for pending in updated.get("pending_fix_ids", []):
        if pending.get("fix_id") == fix_id:
            pending["status"] = "complete" if status == "complete" else "deferred"
            found = True
            break
    if not found:
        raise PQXFixExecutionError(f"fix_id missing from pending_fix_ids: {fix_id}")

    if status == "complete":
        if fix_id not in updated["executed_fixes"]:
            updated["executed_fixes"].append(fix_id)
    else:
        if fix_id not in updated["failed_fixes"]:
            updated["failed_fixes"].append(fix_id)

    updated["fix_artifacts"][fix_id] = fix_result["artifacts"]
    updated["reinsertion_points"][fix_id] = fix_result["insertion_point"]
    return updated


def _required_identity(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise PQXFixExecutionError(f"fix step missing required {label}")
    return value


def _roadmap_from_state(bundle_state: dict) -> list[str]:
    known_steps = set(bundle_state.get("completed_step_ids", []))
    for pending in bundle_state.get("pending_fix_ids", []):
        for step_id in pending.get("affected_step_ids", []):
            known_steps.add(step_id)
    if not known_steps:
        raise PQXFixExecutionError("cannot infer roadmap from empty bundle_state")
    return sorted(known_steps)
