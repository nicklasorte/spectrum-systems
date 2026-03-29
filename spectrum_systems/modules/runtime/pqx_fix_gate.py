"""Deterministic governed fix-completion gate for PQX bundle resume control."""

from __future__ import annotations

from copy import deepcopy

from spectrum_systems.contracts import validate_artifact


class PQXFixGateError(ValueError):
    """Raised when fix adjudication violates fail-closed gate semantics."""


_ALLOWED_PENDING_STATUSES = {"open", "planned", "in_progress", "complete", "deferred", "resolved"}


def validate_fix_resolution_inputs(
    bundle_state: dict,
    fix_execution_record: dict,
    *,
    approved_grouped_fix_targets: dict[str, list[str]] | None = None,
) -> dict:
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
        previous = bundle_state["fix_gate_results"][fix_id]
        if previous.get("gate_status") == "passed":
            raise PQXFixGateError(f"fix gate already passed for fix_id: {fix_id}")

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
            "reasons": ["fix insertion anchor does not map to pending finding target"],
            "pending_fix": pending_fix,
            "allowed_targets": allowed_targets,
        }

    expected_artifacts = bundle_state["fix_artifacts"].get(fix_id)
    if expected_artifacts is not None and expected_artifacts != fix_execution_record["artifacts"]:
        return {
            "mapping_status": "mismatched",
            "resolution_status": "unresolved",
            "reasons": ["fix artifact refs were mutated in place"],
            "pending_fix": pending_fix,
            "allowed_targets": allowed_targets,
        }

    expected_insertion = bundle_state["reinsertion_points"].get(fix_id)
    if expected_insertion is not None and expected_insertion != fix_execution_record["insertion_point"]:
        return {
            "mapping_status": "mismatched",
            "resolution_status": "unresolved",
            "reasons": ["reinsertion point differs from recorded fix execution state"],
            "pending_fix": pending_fix,
            "allowed_targets": allowed_targets,
        }

    if fix_execution_record["execution_status"] != "complete":
        return {
            "mapping_status": "matched",
            "resolution_status": "unresolved",
            "reasons": ["fix execution did not complete"],
            "pending_fix": pending_fix,
            "allowed_targets": allowed_targets,
        }

    if fix_execution_record["validation_result"].lower() not in {"passed", "success", "resolved"}:
        return {
            "mapping_status": "matched",
            "resolution_status": "unresolved",
            "reasons": ["fix execution validation_result indicates unresolved outcome"],
            "pending_fix": pending_fix,
            "allowed_targets": allowed_targets,
        }

    return {
        "mapping_status": "matched",
        "resolution_status": "resolved",
        "reasons": [
            "fix mapped to exactly one pending finding",
            "fix execution artifact validated",
            "reinsertion state consistent",
        ],
        "pending_fix": pending_fix,
        "allowed_targets": allowed_targets,
    }


def determine_fix_gate_status(comparison: dict) -> dict:
    mapping_status = comparison["mapping_status"]
    resolution_status = comparison["resolution_status"]

    gate_status = "passed" if mapping_status == "matched" and resolution_status == "resolved" else "blocked"
    return {
        "gate_status": gate_status,
        "resume_allowed": gate_status == "passed",
        "resolution_status": resolution_status if mapping_status == "matched" else "mismatched",
        "replay_safe": True,
        "reasons": list(dict.fromkeys(comparison["reasons"])),
    }


def emit_fix_gate_record(
    *,
    bundle_state: dict,
    fix_execution_record: dict,
    gate_decision: dict,
    comparison: dict,
    now: str,
) -> dict:
    pending_fix = comparison["pending_fix"]
    record = {
        "schema_version": "1.0.0",
        "fix_id": fix_execution_record["fix_id"],
        "bundle_id": bundle_state["active_bundle_id"],
        "run_id": bundle_state["run_id"],
        "trace_id": fix_execution_record["trace_id"],
        "source_finding_id": pending_fix["source_finding_id"],
        "source_review_id": pending_fix["source_review_id"],
        "execution_status": fix_execution_record["execution_status"],
        "validation_result": fix_execution_record["validation_result"],
        "gate_status": gate_decision["gate_status"],
        "resolution_status": gate_decision["resolution_status"],
        "resume_allowed": gate_decision["resume_allowed"],
        "replay_safe": gate_decision["replay_safe"],
        "matched_pending_fix_ids": [pending_fix["fix_id"]],
        "accepted_target_step_ids": comparison["allowed_targets"],
        "insertion_point": deepcopy(fix_execution_record["insertion_point"]),
        "artifact_refs": deepcopy(fix_execution_record["artifacts"]),
        "reasons": gate_decision["reasons"],
        "created_at": now,
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
        now=now,
    )

    updated = deepcopy(bundle_state)
    fix_id = fix_execution_record["fix_id"]
    record_id = f"fix-gate:{updated['run_id']}:{fix_id}"
    updated["fix_gate_results"][fix_id] = {
        "gate_status": gate_record["gate_status"],
        "record_ref": fix_gate_record_ref,
        "record_id": record_id,
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
