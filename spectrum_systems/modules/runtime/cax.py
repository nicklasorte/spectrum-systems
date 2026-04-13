"""CAX — Control Arbitration eXchange."""

from __future__ import annotations

from typing import Any


def build_arbitration_inputs(*, tax_decision: str, bax_decision: str, tpa_decision: str, required_signals_present: bool, trace_complete: bool, replay_blocking: bool, drift_blocking: bool) -> dict[str, Any]:
    return {
        "tax_decision": tax_decision,
        "bax_decision": bax_decision,
        "tpa_decision": tpa_decision,
        "required_signals_present": bool(required_signals_present),
        "trace_complete": bool(trace_complete),
        "replay_blocking": bool(replay_blocking),
        "drift_blocking": bool(drift_blocking),
    }


def apply_arbitration_precedence(*, inputs: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    tax = str(inputs.get("tax_decision") or "continue")
    bax = str(inputs.get("bax_decision") or "warn")
    tpa = str(inputs.get("tpa_decision") or "allow")

    if tpa == "reject":
        return "block_required", ["tpa_reject"]
    if not inputs.get("required_signals_present", False) or not inputs.get("trace_complete", False):
        return "block_required", ["required_signals_or_trace_missing"]
    if bax == "block":
        return "block_required", ["bax_block"]
    if tax == "block_required":
        return "block_required", ["tax_block"]
    if bax == "freeze":
        return "freeze_required", ["bax_freeze"]
    if tax == "freeze_required":
        return "freeze_required", ["tax_freeze"]
    if tax == "repair_required" and bax in {"allow", "warn"}:
        return "repair_required", ["tax_repair"]
    if tax == "await_async_signal" and bax in {"allow", "warn", "freeze"}:
        return "await_async_signal", ["await_async_signal"]
    if tax == "complete" and bax == "allow" and not inputs.get("replay_blocking", False) and tpa != "reject" and not inputs.get("drift_blocking", False):
        return "complete", ["tax_complete_bax_allow"]
    if tax == "complete" and bax == "warn":
        return "warn_complete_candidate", ["tax_complete_bax_warn"]
    return "continue", ["default_continue"]


def resolve_authority_conflicts(*, inputs: dict[str, Any]) -> dict[str, Any]:
    outcome, reason_codes = apply_arbitration_precedence(inputs=inputs)
    return {"outcome": outcome, "reason_codes": reason_codes}


def emit_control_arbitration_record(*, run_id: str, trace_id: str, policy_version: str, reason_bundle_ref: str, input_refs: dict[str, str], inputs: dict[str, Any]) -> dict[str, Any]:
    resolved = resolve_authority_conflicts(inputs=inputs)
    return {
        "artifact_type": "control_arbitration_record",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "arbitration_id": f"CAR-{run_id}-{trace_id}",
        "run_id": run_id,
        "trace_id": trace_id,
        "outcome": resolved["outcome"],
        "reason_bundle_ref": reason_bundle_ref,
        "input_refs": input_refs,
        "policy_version": policy_version,
    }


def emit_cde_arbitration_input_bundle(*, arbitration_record: dict[str, Any], blocking_conditions: list[str]) -> dict[str, Any]:
    return {
        "artifact_type": "cde_arbitration_input_bundle",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "bundle_id": f"CDEIN-{arbitration_record['run_id']}-{arbitration_record['trace_id']}",
        "run_id": arbitration_record["run_id"],
        "trace_id": arbitration_record["trace_id"],
        "arbitration_ref": f"control_arbitration_record:{arbitration_record['arbitration_id']}",
        "recommended_outcome": arbitration_record["outcome"],
        "blocking_conditions": list(blocking_conditions),
    }
