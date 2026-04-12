"""TLC hardening helpers for bounded orchestration, routing integrity, and replayable trust checks."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any

from spectrum_systems.contracts import validate_artifact


class TLCHardeningError(ValueError):
    """Raised when TLC hardening invariants fail closed."""


def _hash(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_tlc_routing_bundle(*, run_id: str, trace_id: str, governed_inputs: dict[str, Any], created_at: str) -> dict[str, Any]:
    required = ["build_admission_record", "normalized_execution_request", "tlc_handoff_record"]
    missing = [name for name in required if not isinstance(governed_inputs.get(name), dict)]
    if missing:
        raise TLCHardeningError(f"routing_bundle_missing_inputs:{','.join(missing)}")

    handoff = governed_inputs["tlc_handoff_record"]
    path = list(handoff.get("lineage", {}).get("intended_path", []))
    if path != ["TLC", "TPA", "PQX"]:
        raise TLCHardeningError("routing_bundle_invalid_lineage_path")

    bundle = {
        "artifact_type": "tlc_routing_bundle",
        "schema_version": "1.0.0",
        "bundle_id": f"trb-{_hash([run_id, trace_id, path])[:16]}",
        "run_id": run_id,
        "trace_id": trace_id,
        "route_class": "repo_write_governed",
        "target_system": "TPA",
        "route_reason_codes": ["aex_admission_verified", "repo_write_requires_tpa_policy_gate"],
        "input_refs": [
            f"build_admission_record:{governed_inputs['build_admission_record'].get('admission_id')}",
            f"normalized_execution_request:{governed_inputs['normalized_execution_request'].get('request_id')}",
            f"tlc_handoff_record:{handoff.get('handoff_id')}",
        ],
        "lineage_path": ["AEX", "TLC", "TPA", "PQX"],
        "handoff_disposition": "route",
        "non_authority_assertions": [
            "tlc_not_policy_authority",
            "tlc_not_execution_authority",
            "tlc_not_closure_authority",
        ],
        "created_at": created_at,
    }
    validate_artifact(bundle, "tlc_routing_bundle")
    return bundle


def evaluate_tlc_routing_bundle(*, routing_bundle: dict[str, Any], required_artifacts: dict[str, Any], created_at: str) -> dict[str, Any]:
    checks = {
        "handoff_completeness": bool(required_artifacts.get("tlc_handoff_record")),
        "route_validity": routing_bundle.get("target_system") in {"TPA", "RQX", "CDE", "SEL", "FRE", "RIL", "PRG"},
        "required_artifacts_present": all(bool(required_artifacts.get(key)) for key in ("build_admission_record", "normalized_execution_request", "tlc_handoff_record")),
        "authority_boundary_correct": "tlc_not_closure_authority" in routing_bundle.get("non_authority_assertions", []),
    }
    fail_reasons = [name for name, status in checks.items() if not status]
    result = {
        "artifact_type": "tlc_routing_eval_result",
        "schema_version": "1.0.0",
        "eval_id": f"tre-{_hash([routing_bundle.get('bundle_id'), checks])[:16]}",
        "bundle_ref": f"tlc_routing_bundle:{routing_bundle.get('bundle_id')}",
        "evaluated_at": created_at,
        "evaluation_status": "pass" if not fail_reasons else "fail",
        "checks": checks,
        "fail_reasons": fail_reasons,
        "trace_id": str(routing_bundle.get("trace_id") or "unknown"),
    }
    validate_artifact(result, "tlc_routing_eval_result")
    return result


def validate_cross_system_handoff_integrity(*, routing_bundle: dict[str, Any], expected_trace_id: str) -> list[str]:
    fails: list[str] = []
    if routing_bundle.get("trace_id") != expected_trace_id:
        fails.append("trace_mismatch")
    if routing_bundle.get("lineage_path") != ["AEX", "TLC", "TPA", "PQX"]:
        fails.append("lineage_path_drift")
    if routing_bundle.get("target_system") != "TPA":
        fails.append("repo_write_wrong_target")
    return fails


def validate_tlc_routing_replay(*, prior_bundle: dict[str, Any], replay_bundle: dict[str, Any], prior_eval: dict[str, Any], replay_eval: dict[str, Any]) -> tuple[bool, list[str]]:
    input_fp = _hash({k: prior_bundle.get(k) for k in ("run_id", "trace_id", "route_class", "lineage_path", "target_system")})
    replay_fp = _hash({k: replay_bundle.get(k) for k in ("run_id", "trace_id", "route_class", "lineage_path", "target_system")})
    out_fp = _hash(prior_eval.get("fail_reasons", []))
    replay_out_fp = _hash(replay_eval.get("fail_reasons", []))
    ok = input_fp == replay_fp and out_fp == replay_out_fp
    return ok, ([] if ok else ["routing_replay_mismatch"])


def enforce_prep_vs_authority_integrity(*, artifact_refs: list[str], non_authority_assertions: list[str]) -> list[str]:
    fails: list[str] = []
    if any(ref.startswith("closure_decision_artifact:") for ref in artifact_refs):
        fails.append("prep_artifact_substitutes_closure_authority")
    if any(ref.startswith("tpa_policy_decision_record:") for ref in artifact_refs):
        fails.append("prep_artifact_substitutes_policy_authority")
    if "tlc_not_closure_authority" not in non_authority_assertions:
        fails.append("missing_non_authority_assertion")
    return fails


def detect_handoff_dead_loop(*, route_sequence: list[str]) -> list[str]:
    fails: list[str] = []
    if len(route_sequence) >= 4 and route_sequence[-4:] in (["TLC", "RQX", "TLC", "RQX"], ["TLC", "FRE", "TLC", "FRE"]):
        fails.append("handoff_dead_loop_detected")
    return fails


def detect_owner_boundary_leakage(*, claimed_owner_actions: list[str]) -> list[str]:
    forbidden_prefixes = ("execute_work_slice", "closure_decision", "policy_admission", "review_interpretation")
    return [f"owner_boundary_leakage:{action}" for action in claimed_owner_actions if action.startswith(forbidden_prefixes)]


def track_handoff_debt(*, dispositions: list[dict[str, Any]], trace_id: str, created_at: str) -> dict[str, Any]:
    unresolved = sum(1 for row in dispositions if row.get("handoff_disposition") in {"hold", "escalate"})
    operator_handoffs = sum(1 for row in dispositions if row.get("target_system") == "RQX")
    reason_counts = Counter()
    for row in dispositions:
        for code in row.get("route_reason_codes", []):
            reason_counts[str(code)] += 1
    reasons = [code for code, c in reason_counts.items() if c > 1]
    status = "critical" if unresolved >= 4 else "elevated" if unresolved >= 2 else "normal"
    artifact = {
        "artifact_type": "tlc_handoff_debt_record",
        "schema_version": "1.0.0",
        "debt_id": f"thd-{_hash([trace_id, unresolved, operator_handoffs])[:16]}",
        "trace_id": trace_id,
        "created_at": created_at,
        "unresolved_count": unresolved,
        "operator_handoff_count": operator_handoffs,
        "debt_status": status,
        "reason_codes": reasons or ["none"],
    }
    validate_artifact(artifact, "tlc_handoff_debt_record")
    return artifact


def validate_route_to_review_integrity(*, routing_bundle: dict[str, Any], handoff_payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if routing_bundle.get("target_system") == "RQX":
        if handoff_payload.get("execution_payload"):
            failures.append("review_handoff_smuggles_execution_semantics")
        if handoff_payload.get("closure_authority"):
            failures.append("review_handoff_smuggles_closure_authority")
    return failures


def validate_route_to_closure_integrity(*, progression_refs: list[str], closure_authority_present: bool) -> list[str]:
    failures: list[str] = []
    if any(ref.startswith("batch_progression:") or ref.startswith("umbrella_progression:") for ref in progression_refs):
        if not closure_authority_present:
            failures.append("progression_artifact_used_without_cde_closure_authority")
    return failures


def build_tlc_orchestration_readiness(*, run_id: str, trace_id: str, routing_eval: dict[str, Any], handoff_failures: list[str], created_at: str) -> dict[str, Any]:
    fail_reasons = list(routing_eval.get("fail_reasons", [])) + list(handoff_failures)
    artifact = {
        "artifact_type": "tlc_orchestration_readiness_record",
        "schema_version": "1.0.0",
        "readiness_id": f"tor-{_hash([run_id, trace_id, fail_reasons])[:16]}",
        "run_id": run_id,
        "trace_id": trace_id,
        "readiness_status": "candidate_only" if not fail_reasons else "blocked",
        "fail_reasons": sorted(set(fail_reasons)),
        "non_authority_assertions": [
            "candidate_only_non_authoritative",
            "does_not_replace_cde_closure_authority",
            "does_not_replace_tpa_policy_authority",
            "does_not_replace_pqx_execution_authority",
        ],
        "created_at": created_at,
    }
    validate_artifact(artifact, "tlc_orchestration_readiness_record")
    return artifact


def compute_tlc_orchestration_effectiveness(*, run_outcomes: list[dict[str, Any]], window_id: str, created_at: str) -> dict[str, Any]:
    if not run_outcomes:
        raise TLCHardeningError("effectiveness_requires_outcomes")
    total = len(run_outcomes)
    progressed = sum(1 for row in run_outcomes if row.get("progressed") is True)
    dead_loops = sum(1 for row in run_outcomes if row.get("dead_loop") is True)
    bypasses = sum(1 for row in run_outcomes if row.get("bypass") is True)
    progression_rate = progressed / total
    dead_loop_rate = dead_loops / total
    bypass_rate = bypasses / total
    if progression_rate >= 0.7 and dead_loop_rate <= 0.1 and bypass_rate == 0:
        status = "improving"
    elif progression_rate < 0.5 or dead_loop_rate > 0.2 or bypass_rate > 0:
        status = "degraded"
    else:
        status = "flat"
    artifact = {
        "artifact_type": "tlc_orchestration_effectiveness_record",
        "schema_version": "1.0.0",
        "effectiveness_id": f"toe-{_hash([window_id, total, progressed, dead_loops, bypasses])[:16]}",
        "window_id": window_id,
        "created_at": created_at,
        "runs_evaluated": total,
        "progression_rate": progression_rate,
        "dead_loop_rate": dead_loop_rate,
        "bypass_rate": bypass_rate,
        "value_status": status,
    }
    validate_artifact(artifact, "tlc_orchestration_effectiveness_record")
    return artifact


def run_tlc_boundary_redteam(*, fixtures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in fixtures if row.get("should_fail_closed") and row.get("observed") != "blocked"]


def run_tlc_semantic_redteam(*, fixtures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings = []
    for row in fixtures:
        if row.get("semantic_drift") and row.get("observed") != "blocked":
            findings.append(row)
    return findings
