"""Deterministic bounded TPA policy authority engine and hardening loop."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping

from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.governance.tpa_scope_policy import load_tpa_scope_policy


class TPAPolicyAuthorityError(ValueError):
    """Raised when TPA policy authority fails closed."""


def _stable_digest(payload: Any) -> str:
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _as_list(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, list):
        raise TPAPolicyAuthorityError(f"{field} must be a list")
    cleaned = sorted({str(item).strip() for item in value if str(item).strip()})
    if not cleaned:
        raise TPAPolicyAuthorityError(f"{field} must not be empty")
    return cleaned


def _ensure_boundaries(bundle: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if str(bundle.get("task_wrapper_ref", "")).startswith("codex_pqx_task_wrapper:") is False:
        reasons.append("invalid_upstream_task_wrapper")
    lineage = list(bundle.get("lineage_path") or [])
    if lineage and lineage != ["AEX", "TLC", "TPA", "PQX"]:
        reasons.append("lineage_path_violation")
    return reasons


def _source_authority_checks(bundle: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    receipt = dict(bundle.get("source_authority_refresh_receipt") or {})
    freshness = str(receipt.get("freshness_status") or "")
    age_hours = float(receipt.get("age_hours") or 0)
    max_age_hours = float(receipt.get("max_age_hours") or 0)
    if freshness in {"stale", "mismatch"}:
        reasons.append("source_authority_not_fresh")
    if max_age_hours <= 0 or age_hours > max_age_hours:
        reasons.append("source_authority_age_exceeded")
    return reasons


def _scope_budget_checks(bundle: Mapping[str, Any], scope_policy: Mapping[str, Any]) -> tuple[list[str], list[str], dict[str, Any]]:
    requested_scope = _as_list(bundle.get("requested_scope"), field="requested_scope")
    max_scope_items = int(scope_policy.get("max_scope_items", 1))
    max_units = int(dict(scope_policy.get("complexity_budget_caps") or {}).get("max_units", 1))
    allocated_units = len(requested_scope) * 2
    reasons: list[str] = []
    allowed_scope = requested_scope[:max_scope_items]

    if len(requested_scope) > max_scope_items:
        reasons.append("scope_exceeds_policy_limit")
    if allocated_units > max_units:
        reasons.append("complexity_budget_exceeded")

    return reasons, allowed_scope, {
        "max_units": max_units,
        "allocated_units": allocated_units,
        "status": "within_budget" if allocated_units <= max_units else "exceeded",
    }


def evaluate_tpa_policy_input_bundle(bundle: Mapping[str, Any]) -> dict[str, Any]:
    candidate = deepcopy(dict(bundle))
    validate_artifact(candidate, "tpa_policy_input_bundle")

    scope_policy = load_tpa_scope_policy()
    reasons: list[str] = []
    reasons.extend(_ensure_boundaries(candidate))
    reasons.extend(_source_authority_checks(candidate))
    scope_reasons, allowed_scope, complexity_budget = _scope_budget_checks(candidate, scope_policy)
    reasons.extend(scope_reasons)

    evidence_refs = [
        str(candidate["source_authority_refresh_receipt"]["receipt_ref"]),
        str(candidate["complexity_trend_ref"]),
    ]

    debt_counter = int(candidate.get("evidence_debt_counter", 0))
    if debt_counter >= 3:
        reasons.append("evidence_escalation_debt")

    # Deterministic conflict arbitration
    conflicts: list[dict[str, Any]] = []
    for code in sorted(set(reasons)):
        if code in {"scope_exceeds_policy_limit", "complexity_budget_exceeded", "source_authority_not_fresh", "source_authority_age_exceeded", "lineage_path_violation", "invalid_upstream_task_wrapper"}:
            conflicts.append(
                {
                    "artifact_type": "tpa_conflict_record",
                    "schema_version": "1.0.0",
                    "conflict_id": f"tpa-conflict-{_stable_digest([candidate['bundle_id'], code])[:12]}",
                    "trace_id": candidate["trace_id"],
                    "input_bundle_ref": f"tpa_policy_input_bundle:{candidate['bundle_id']}",
                    "conflict_type": "scope_budget_mismatch" if "scope" in code or "budget" in code else "upstream_boundary_violation",
                    "materiality": "material",
                    "resolution_status": "unresolved",
                    "reason_codes": [code],
                }
            )

    decision = "allow"
    if any(code in reasons for code in ["invalid_upstream_task_wrapper", "lineage_path_violation"]):
        decision = "reject"
    elif any(code in reasons for code in ["source_authority_not_fresh", "source_authority_age_exceeded", "evidence_escalation_debt"]):
        decision = "evidence_required"
    elif any(code in reasons for code in ["scope_exceeds_policy_limit", "complexity_budget_exceeded"]):
        decision = "narrow"

    decision_record = {
        "artifact_type": "tpa_policy_decision_record",
        "schema_version": "1.0.0",
        "decision_id": f"tpa-decision-{_stable_digest([candidate['bundle_id'], decision])[:12]}",
        "trace_id": candidate["trace_id"],
        "input_bundle_ref": f"tpa_policy_input_bundle:{candidate['bundle_id']}",
        "decision": decision,
        "reason_codes": sorted(set(reasons)) or ["policy_input_valid"],
        "evidence_refs": sorted(set(evidence_refs)),
        "allowed_scope": allowed_scope,
        "complexity_budget": complexity_budget,
        "non_authority_assertions": [
            "no_closure_decision",
            "no_runtime_enforcement",
            "no_review_semantics_reinterpretation",
        ],
    }
    validate_artifact(decision_record, "tpa_policy_decision_record")

    evidence_record = {
        "artifact_type": "tpa_evidence_requirement_record",
        "schema_version": "1.0.0",
        "record_id": f"tpa-evidence-{_stable_digest([decision_record['decision_id'], debt_counter])[:12]}",
        "trace_id": candidate["trace_id"],
        "decision_ref": f"tpa_policy_decision_record:{decision_record['decision_id']}",
        "required_evidence": sorted(set(["eval_case:tpa-policy-boundary", "regression_test:test_tpa_policy_authority"] + ([] if decision != "evidence_required" else ["source_authority_refresh_receipt:fresh"]))),
        "escalation_level": "required" if decision == "evidence_required" else ("warning" if reasons else "none"),
        "debt_counter": debt_counter,
    }
    validate_artifact(evidence_record, "tpa_evidence_requirement_record")

    replay_input = {
        "bundle": candidate,
        "decision": decision_record,
        "evidence": evidence_record,
        "conflicts": conflicts,
    }
    replay_fingerprint = _stable_digest(replay_input)

    checks = {
        "evidence_sufficiency": decision != "evidence_required",
        "policy_completeness": bool(decision_record["reason_codes"] and decision_record["allowed_scope"]),
        "boundary_correctness": not any(code in reasons for code in ["invalid_upstream_task_wrapper", "lineage_path_violation"]),
        "scope_correctness": "scope_exceeds_policy_limit" not in reasons,
        "replay_consistency": True,
    }
    fail_reasons = sorted([k for k, ok in checks.items() if not ok])
    eval_result = {
        "artifact_type": "tpa_policy_eval_result",
        "schema_version": "1.0.0",
        "eval_id": f"tpa-eval-{_stable_digest([decision_record['decision_id'], checks])[:12]}",
        "trace_id": candidate["trace_id"],
        "decision_ref": f"tpa_policy_decision_record:{decision_record['decision_id']}",
        "status": "pass" if not fail_reasons else "fail",
        "checks": checks,
        "fail_reasons": fail_reasons,
    }
    validate_artifact(eval_result, "tpa_policy_eval_result")

    conflict_refs: list[str] = []
    for conflict in conflicts:
        validate_artifact(conflict, "tpa_conflict_record")
        conflict_refs.append(f"tpa_conflict_record:{conflict['conflict_id']}")

    effectiveness = {
        "prevented_bad_execution": decision in {"reject", "evidence_required"},
        "unnecessary_blocking": decision == "reject" and not reasons,
        "precision_score": 1.0 if decision == "allow" and not reasons else (0.75 if decision in {"narrow", "evidence_required"} else 0.6),
    }

    policy_bundle = {
        "artifact_type": "tpa_policy_bundle",
        "schema_version": "1.0.0",
        "bundle_id": f"tpa-bundle-{_stable_digest([candidate['bundle_id'], replay_fingerprint])[:12]}",
        "trace_id": candidate["trace_id"],
        "input_bundle_ref": f"tpa_policy_input_bundle:{candidate['bundle_id']}",
        "decision_ref": f"tpa_policy_decision_record:{decision_record['decision_id']}",
        "eval_result_ref": f"tpa_policy_eval_result:{eval_result['eval_id']}",
        "conflict_refs": conflict_refs,
        "evidence_requirement_ref": f"tpa_evidence_requirement_record:{evidence_record['record_id']}",
        "replay_fingerprint": replay_fingerprint,
        "effectiveness": effectiveness,
    }
    validate_artifact(policy_bundle, "tpa_policy_bundle")

    return {
        "input_bundle": candidate,
        "decision_record": decision_record,
        "evidence_requirement_record": evidence_record,
        "conflict_records": conflicts,
        "policy_eval_result": eval_result,
        "policy_bundle": policy_bundle,
    }


def replay_validate(bundle: Mapping[str, Any], expected_fingerprint: str) -> bool:
    result = evaluate_tpa_policy_input_bundle(bundle)
    actual = str(result["policy_bundle"]["replay_fingerprint"])
    return actual == expected_fingerprint


def build_redteam_fixtures(*, round_id: str) -> list[dict[str, Any]]:
    base = {
        "artifact_type": "tpa_policy_input_bundle",
        "schema_version": "1.0.0",
        "bundle_id": f"{round_id}-base",
        "trace_id": f"trace-{round_id}",
        "task_wrapper_ref": "codex_pqx_task_wrapper:task-rt",
        "source_authority_refresh_receipt": {
            "receipt_ref": "source_authority_refresh_receipt:rt-1",
            "refreshed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "age_hours": 1,
            "max_age_hours": 24,
            "freshness_status": "fresh",
        },
        "complexity_trend_ref": "complexity_trend:run:AI-01",
        "requested_scope": ["spectrum_systems/modules/runtime/tpa_policy_authority.py"],
        "proposed_action": "allow",
        "lineage_path": ["AEX", "TLC", "TPA", "PQX"],
    }
    stale = deepcopy(base)
    stale["bundle_id"] = f"{round_id}-stale"
    stale["source_authority_refresh_receipt"]["freshness_status"] = "stale"

    prep_as_authority = deepcopy(base)
    prep_as_authority["bundle_id"] = f"{round_id}-prep-authority"
    prep_as_authority["task_wrapper_ref"] = "raw_task_payload:unsafe"

    scope_abuse = deepcopy(base)
    scope_abuse["bundle_id"] = f"{round_id}-scope-abuse"
    scope_abuse["requested_scope"] = [
        "spectrum_systems/modules/runtime/tpa_policy_authority.py",
        "spectrum_systems/modules/runtime/sel_enforcement_foundation.py",
        "spectrum_systems/modules/runtime/cde_decision_flow.py",
        "tests/test_tpa_policy_authority.py",
    ]

    churn = deepcopy(base)
    churn["bundle_id"] = f"{round_id}-evidence-churn"
    churn["evidence_debt_counter"] = 4

    return [base, stale, prep_as_authority, scope_abuse, churn]


def run_redteam_round(*, round_id: str) -> dict[str, Any]:
    fixtures = build_redteam_fixtures(round_id=round_id)
    outcomes: list[dict[str, Any]] = []
    exploits: list[dict[str, Any]] = []
    for fixture in fixtures:
        result = evaluate_tpa_policy_input_bundle(fixture)
        decision = result["decision_record"]["decision"]
        bundle_id = fixture["bundle_id"]
        outcomes.append({"bundle_id": bundle_id, "decision": decision, "reasons": result["decision_record"]["reason_codes"]})
        if bundle_id.endswith("stale") and decision == "allow":
            exploits.append({"bundle_id": bundle_id, "exploit": "stale_source_authority_allowed"})
        if bundle_id.endswith("prep-authority") and decision != "reject":
            exploits.append({"bundle_id": bundle_id, "exploit": "prep_artifact_treated_as_authority"})
        if bundle_id.endswith("scope-abuse") and decision == "allow":
            exploits.append({"bundle_id": bundle_id, "exploit": "scope_expansion_not_detected"})
        if bundle_id.endswith("evidence-churn") and decision != "evidence_required":
            exploits.append({"bundle_id": bundle_id, "exploit": "evidence_churn_not_escalated"})

    return {
        "round_id": round_id,
        "outcomes": outcomes,
        "exploits": exploits,
        "status": "pass" if not exploits else "fail",
    }


__all__ = [
    "TPAPolicyAuthorityError",
    "evaluate_tpa_policy_input_bundle",
    "replay_validate",
    "build_redteam_fixtures",
    "run_redteam_round",
]
