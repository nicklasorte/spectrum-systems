"""MNT-25..MNT-29 deterministic enforcement coverage/runtime checks."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from spectrum_systems.contracts import validate_artifact


REQUIRED_PROMOTION_ENTRYPOINTS = {
    "promotion_gate",
    "release_gate",
    "control_loop_certification",
}

_ALLOWED_ENFORCEMENT_STATES = {"pass", "freeze", "block"}


def audit_promotion_entrypoints(*, observed_entrypoints: set[str], created_at: str) -> dict[str, Any]:
    uncovered = sorted(REQUIRED_PROMOTION_ENTRYPOINTS - observed_entrypoints)
    rec = {
        "artifact_type": "mnt_promotion_entrypoint_coverage_report",
        "artifact_id": "mnt-entrypoint-audit-001",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.3.131",
        "created_at": created_at,
        "entrypoints": sorted(observed_entrypoints),
        "uncovered_entrypoints": uncovered,
        "status": "pass" if not uncovered else "fail",
    }
    validate_artifact(rec, "mnt_promotion_entrypoint_coverage_report")
    return rec


def enforce_promotion_entrypoint(
    *,
    entrypoint: str,
    mnt_002_executed: bool,
    certification_bundle_ref: str | None,
    created_at: str,
    artifact_id: str = "mnt-promotion-guard-001",
) -> dict[str, Any]:
    blocked_reasons: list[str] = []
    if entrypoint not in REQUIRED_PROMOTION_ENTRYPOINTS:
        blocked_reasons.append("unknown_promotion_entrypoint")
    if not mnt_002_executed:
        blocked_reasons.append("mnt_002_required_before_advancement")
    if not certification_bundle_ref:
        blocked_reasons.append("missing_certification_bundle")

    status = "pass" if not blocked_reasons else "block"
    rec = {
        "artifact_type": "mnt_promotion_enforcement_result",
        "artifact_id": artifact_id,
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.3.131",
        "created_at": created_at,
        "entrypoint": entrypoint,
        "mnt_002_executed": mnt_002_executed,
        "certification_bundle_ref": certification_bundle_ref,
        "status": status,
        "blocked_reasons": blocked_reasons,
    }
    validate_artifact(rec, "mnt_promotion_enforcement_result")
    return rec


def audit_advancement_path_coverage(
    *, required_paths: Iterable[str], audited_paths: Iterable[str], created_at: str, artifact_id: str = "mnt-advancement-audit-001"
) -> dict[str, Any]:
    required = sorted({str(v) for v in required_paths if str(v).strip()})
    audited = sorted({str(v) for v in audited_paths if str(v).strip()})
    uncovered = sorted(set(required) - set(audited))
    rec = {
        "artifact_type": "mnt_advancement_coverage_audit",
        "artifact_id": artifact_id,
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.3.131",
        "created_at": created_at,
        "required_paths": required,
        "audited_paths": audited,
        "uncovered_paths": uncovered,
        "complete": not uncovered,
    }
    validate_artifact(rec, "mnt_advancement_coverage_audit")
    return rec


def consistency_check(*, gate_results: Mapping[str, str], created_at: str) -> dict[str, Any]:
    inconsistent = sorted([gate for gate, state in gate_results.items() if state not in _ALLOWED_ENFORCEMENT_STATES])
    rec = {
        "artifact_type": "mnt_enforcement_consistency_result",
        "artifact_id": "mnt-consistency-001",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.3.131",
        "created_at": created_at,
        "checked_gates": sorted(gate_results.keys()),
        "inconsistent_gates": inconsistent,
        "status": "pass" if not inconsistent else "fail",
    }
    validate_artifact(rec, "mnt_enforcement_consistency_result")
    return rec


def validate_real_flow(*, flow_id: str, step_results: Mapping[str, str], created_at: str, artifact_id: str = "mnt-flow-001") -> dict[str, Any]:
    reason_codes = sorted([f"{step}:invalid_state" for step, value in step_results.items() if value not in _ALLOWED_ENFORCEMENT_STATES])
    status = "pass" if not reason_codes else "fail"
    rec = {
        "artifact_type": "mnt_real_flow_reliability_result",
        "artifact_id": artifact_id,
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.3.131",
        "created_at": created_at,
        "flow_id": flow_id,
        "steps_checked": sorted(step_results.keys()),
        "status": status,
        "reason_codes": reason_codes or ["all_steps_enforced"],
    }
    validate_artifact(rec, "mnt_real_flow_reliability_result")
    return rec


def run_mnt_red_team_round(*, round_id: str, exploits: list[dict[str, Any]], generated_at: str, artifact_id: str = "mnt-rt-round-001") -> dict[str, Any]:
    exploit_ids = sorted(str(item.get("exploit_id") or "unknown") for item in exploits)
    tests_converted = all(bool(item.get("guard_test_id")) for item in exploits)
    evals_converted = all(bool(item.get("eval_case_id")) for item in exploits)
    guards_converted = all(bool(item.get("guard_rule_id")) for item in exploits)
    rec = {
        "artifact_type": "mnt_red_team_round_report",
        "artifact_id": artifact_id,
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "1.3.131",
        "round_id": round_id,
        "generated_at": generated_at,
        "exploit_count": len(exploits),
        "exploits": exploit_ids,
        "all_exploits_converted_to_tests": tests_converted,
        "all_exploits_converted_to_evals": evals_converted,
        "all_exploits_converted_to_guards": guards_converted,
    }
    validate_artifact(rec, "mnt_red_team_round_report")
    return rec
