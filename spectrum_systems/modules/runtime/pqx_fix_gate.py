"""Deterministic governed fix-completion gate for PQX bundle resume control."""

from __future__ import annotations

from copy import deepcopy

from spectrum_systems.contracts import validate_artifact


class PQXFixGateError(ValueError):
    """Raised when fix adjudication violates fail-closed gate semantics."""


_ALLOWED_PENDING_STATUSES = {"open", "planned", "in_progress", "complete", "deferred", "resolved"}
_ALLOWED_GATE_STATUS = {"passed", "blocked"}


def validate_fix_resolution_inputs(
    bundle_state: dict,
    fix_execution_record: dict,
    *,
    approved_grouped_fix_targets: dict[str, list[str]] | None = None,
) -> dict[str, list[str]]:
    if not isinstance(bundle_state, dict):
        raise PQXFixGateError("bundle_state must be an object")
    if not isinstance(fix_execution_record, dict):
        raise PQXFixGateError("fix_execution_record must be an object")

    try:
        validate_artifact(fix_execution_record, "pqx_fix_execution_record")
    except Exception as exc:
        raise PQXFixGateError(f"invalid pqx_fix_execution_record artifact: {exc}") from exc

    required_state_fields = {
        "pending_fix_ids",
        "fix_artifacts",
        "reinsertion_points",
        "fix_gate_results",
        "resolved_fixes",
        "unresolved_fixes",
        "last_fix_gate_status",
        "run_id",
        "active_bundle_id",
    }
    missing = sorted(required_state_fields - set(bundle_state.keys()))
    if missing:
        raise PQXFixGateError(f"bundle_state missing required fix gate fields: {missing}")

    if fix_execution_record["run_id"] != bundle_state["run_id"]:
        raise PQXFixGateError("fix_execution_record run_id does not match bundle_state run_id")

    pending = bundle_state["pending_fix_ids"]
    if not isinstance(pending, list):
        raise PQXFixGateError("pending_fix_ids must be a list")
    for entry in pending:
        if not isinstance(entry, dict):
            raise PQXFixGateError("pending_fix_ids entries must be objects")
        if entry.get("status") not in _ALLOWED_PENDING_STATUSES:
            raise PQXFixGateError(f"pending fix has unsupported status: {entry.get('status')}")

    grouped = approved_grouped_fix_targets or {}
    if not isinstance(grouped, dict):
        raise PQXFixGateError("approved_grouped_fix_targets must be a mapping")
    for key, value in grouped.items():
        if not isinstance(key, str) or not key:
            raise PQXFixGateError("approved_grouped_fix_targets keys must be non-empty strings")
        if not isinstance(value, list) or not value or any(not isinstance(step, str) or not step for step in value):
            raise PQXFixGateError("approved_grouped_fix_targets values must be non-empty string lists")

    return grouped


def compare_fix_result_to_pending_finding(
    bundle_state: dict,
    fix_execution_record: dict,
    *,
    approved_grouped_fix_targets: dict[str, list[str]] | None = None,
) -> dict:
    grouped = validate_fix_resolution_inputs(
        bundle_state,
        fix_execution_record,
        approved_grouped_fix_targets=approved_grouped_fix_targets,
    )

    fix_id = fix_execution_record["fix_id"]
    matches = [f for f in bundle_state["pending_fix_ids"] if f.get("fix_id") == fix_id]
    if len(matches) != 1:
        raise PQXFixGateError("executed fix must map to exactly one pending finding")
    pending_fix = matches[0]

    if fix_id in bundle_state["resolved_fixes"]:
        raise PQXFixGateError(f"duplicate resolution attempt for fix_id: {fix_id}")

    if fix_id in bundle_state["fix_gate_results"]:
        raise PQXFixGateError(f"duplicate fix gate persistence attempt for fix_id: {fix_id}")

    pending_targets = pending_fix.get("affected_step_ids", [])
    if not isinstance(pending_targets, list) or not pending_targets:
        raise PQXFixGateError("pending fix missing affected_step_ids")

    grouped_targets = grouped.get(fix_id)
    if grouped_targets is not None:
        allowed_targets = sorted(set(pending_targets) | set(grouped_targets))
    else:
        allowed_targets = sorted(set(pending_targets))

    insertion_anchor = fix_execution_record["insertion_point"]["anchor_step_id"]
    if insertion_anchor not in allowed_targets:
        return {
            "mapping_status": "mismatched",
            "resolution_status": "unresolved",
            "blocking_reason": "fix insertion anchor does not map to pending finding target",
            "reason_codes": ["LINKAGE_MISMATCH"],
            "pending_fix": pending_fix,
            "allowed_targets": allowed_targets,
            "replay_safe": True,
        }

    expected_artifacts = bundle_state["fix_artifacts"].get(fix_id)
    if expected_artifacts is not None and expected_artifacts != fix_execution_record["artifacts"]:
        return {
            "mapping_status": "mismatched",
            "resolution_status": "unresolved",
            "blocking_reason": "fix artifact refs were mutated in place",
            "reason_codes": ["ARTIFACT_DRIFT"],
            "pending_fix": pending_fix,
            "allowed_targets": allowed_targets,
            "replay_safe": True,
        }

    expected_insertion = bundle_state["reinsertion_points"].get(fix_id)
    if expected_insertion is not None and expected_insertion != fix_execution_record["insertion_point"]:
        return {
            "mapping_status": "mismatched",
            "resolution_status": "unresolved",
            "blocking_reason": "reinsertion point differs from recorded fix execution state",
            "reason_codes": ["INSERTION_DRIFT"],
            "pending_fix": pending_fix,
            "allowed_targets": allowed_targets,
            "replay_safe": True,
        }

    if fix_execution_record["execution_status"] != "complete":
        return {
            "mapping_status": "matched",
            "resolution_status": "unresolved",
            "blocking_reason": "fix execution did not complete",
            "reason_codes": ["EXECUTION_NOT_COMPLETE"],
            "pending_fix": pending_fix,
            "allowed_targets": allowed_targets,
            "replay_safe": True,
        }

    if fix_execution_record["validation_result"].lower() not in {"passed", "success", "resolved"}:
        return {
            "mapping_status": "matched",
            "resolution_status": "unresolved",
            "blocking_reason": "fix execution validation_result indicates unresolved outcome",
            "reason_codes": ["VALIDATION_UNRESOLVED"],
            "pending_fix": pending_fix,
            "allowed_targets": allowed_targets,
            "replay_safe": True,
        }

    return {
        "mapping_status": "matched",
        "resolution_status": "resolved",
        "blocking_reason": None,
        "reason_codes": ["RESOLUTION_VERIFIED"],
        "pending_fix": pending_fix,
        "allowed_targets": allowed_targets,
        "replay_safe": True,
    }


def determine_fix_gate_status(comparison: dict) -> dict:
    mapping_status = comparison["mapping_status"]
    resolution_status = comparison["resolution_status"]
    if mapping_status not in {"matched", "mismatched"}:
        raise PQXFixGateError("comparison mapping_status is malformed")
    if resolution_status not in {"resolved", "unresolved"}:
        raise PQXFixGateError("comparison resolution_status is malformed")

    gate_status = "passed" if mapping_status == "matched" and resolution_status == "resolved" else "blocked"
    if gate_status not in _ALLOWED_GATE_STATUS:
        raise PQXFixGateError("computed gate_status is malformed")
    return {
        "gate_status": gate_status,
        "allows_resume": gate_status == "passed",
        "blocking_reason": comparison["blocking_reason"],
        "replay_safe": comparison["replay_safe"] is True,
        "reason_codes": list(dict.fromkeys(comparison["reason_codes"])),
    }


def emit_fix_gate_record(
    *,
    bundle_state: dict,
    fix_execution_record: dict,
    gate_decision: dict,
    comparison: dict,
    fix_execution_record_ref: str,
    now: str,
) -> dict:
    pending_fix = comparison["pending_fix"]
    review_id = pending_fix.get("source_review_id")
    finding_id = pending_fix.get("source_finding_id")
    record = {
        "schema_version": "1.1.0",
        "fix_gate_id": f"fix-gate:{bundle_state['run_id']}:{fix_execution_record['fix_id']}",
        "created_at": now,
        "run_id": bundle_state["run_id"],
        "trace_id": fix_execution_record["trace_id"],
        "bundle_id": bundle_state["active_bundle_id"],
        "fix_id": fix_execution_record["fix_id"],
        "originating_pending_fix_id": pending_fix["fix_id"],
        "originating_review_artifact_id": review_id,
        "originating_finding_id": finding_id,
        "fix_execution_record_ref": fix_execution_record_ref,
        "adjudication_inputs": {
            "execution_status": fix_execution_record["execution_status"],
            "validation_result": fix_execution_record["validation_result"],
            "accepted_target_step_ids": comparison["allowed_targets"],
            "insertion_point": deepcopy(fix_execution_record["insertion_point"]),
            "artifact_refs": deepcopy(fix_execution_record["artifacts"]),
        },
        "gate_status": gate_decision["gate_status"],
        "allows_resume": gate_decision["allows_resume"],
        "blocking_reason": gate_decision["blocking_reason"],
        "comparison_summary": {
            "mapping_status": comparison["mapping_status"],
            "resolution_status": comparison["resolution_status"],
            "reason_codes": gate_decision["reason_codes"],
            "replay_safe": gate_decision["replay_safe"],
        },
        "producer": {
            "module": "spectrum_systems.modules.runtime.pqx_fix_gate",
            "function": "evaluate_fix_completion",
        },
    }
    try:
        validate_artifact(record, "pqx_fix_gate_record")
    except Exception as exc:
        raise PQXFixGateError(f"invalid pqx_fix_gate_record artifact: {exc}") from exc
    return record


def evaluate_fix_completion(
    *,
    bundle_state: dict,
    fix_execution_record: dict,
    fix_execution_record_ref: str,
    fix_gate_record_ref: str,
    now: str,
    approved_grouped_fix_targets: dict[str, list[str]] | None = None,
) -> tuple[dict, dict]:
    before = deepcopy(bundle_state)
    comparison = compare_fix_result_to_pending_finding(
        bundle_state,
        fix_execution_record,
        approved_grouped_fix_targets=approved_grouped_fix_targets,
    )
    gate_decision = determine_fix_gate_status(comparison)
    gate_record = emit_fix_gate_record(
        bundle_state=bundle_state,
        fix_execution_record=fix_execution_record,
        gate_decision=gate_decision,
        comparison=comparison,
        fix_execution_record_ref=fix_execution_record_ref,
        now=now,
    )

    updated = deepcopy(bundle_state)
    fix_id = fix_execution_record["fix_id"]
    updated["fix_gate_results"][fix_id] = {
        "gate_status": gate_record["gate_status"],
        "record_ref": fix_gate_record_ref,
        "record_id": gate_record["fix_gate_id"],
    }
    updated["last_fix_gate_status"] = gate_record["gate_status"]

    if gate_record["gate_status"] == "passed":
        for fix in updated["pending_fix_ids"]:
            if fix.get("fix_id") == fix_id:
                fix["status"] = "resolved"
                break
        if fix_id not in updated["resolved_fixes"]:
            updated["resolved_fixes"].append(fix_id)
        updated["unresolved_fixes"] = [f for f in updated["unresolved_fixes"] if f != fix_id]
    else:
        if fix_id not in updated["unresolved_fixes"]:
            updated["unresolved_fixes"].append(fix_id)

    if before.get("fix_artifacts", {}).get(fix_id) != updated.get("fix_artifacts", {}).get(fix_id):
        raise PQXFixGateError("fix gate mutated prior fix execution artifacts in place")

    return updated, gate_record


def assert_fix_gate_allows_resume(bundle_state: dict) -> None:
    if bundle_state.get("last_fix_gate_status") != "passed":
        raise PQXFixGateError("bundle resume blocked: last fix gate status is not passed")
    unresolved = bundle_state.get("unresolved_fixes", [])
    if unresolved:
        raise PQXFixGateError(f"bundle resume blocked: unresolved fix gate results remain: {sorted(set(unresolved))}")
