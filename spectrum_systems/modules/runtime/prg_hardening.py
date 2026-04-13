"""PRG bounded program-governance hardening with deterministic recommendation/eval/replay loops."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any, Mapping

from spectrum_systems.contracts import validate_artifact


class PRGHardeningError(ValueError):
    """Raised when PRG governance checks fail closed."""


_FORBIDDEN_ACTION_PREFIXES = (
    "execute_work",
    "admission_gate",
    "enforce_runtime_block",
    "issue_closure",
    "issue_policy",
    "interpret_review_packet",
)


ALLOWED_UPSTREAM_INPUTS = {
    "roadmap_signal_bundle",
    "roadmap_review_view_artifact",
    "batch_delivery_report",
    "evaluation_pattern_signal",
    "trust_posture_snapshot",
    "program_alignment_input",
}

ALLOWED_DOWNSTREAM_OUTPUTS = {
    "evaluation_pattern_report",
    "policy_change_candidate",
    "slice_contract_update_candidate",
    "program_alignment_assessment",
    "prioritized_adoption_candidate_set",
    "adaptive_readiness_record",
    "program_roadmap_alignment_result",
    "prg_governance_eval_result",
    "prg_governance_readiness_record",
    "prg_governance_conflict_record",
    "prg_governance_effectiveness_record",
    "prg_recommendation_rework_debt_record",
    "prg_governance_bundle",
}


def _hash(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def enforce_prg_boundary(*, consumed_inputs: list[str], emitted_outputs: list[str], claimed_actions: list[str]) -> list[str]:
    failures: list[str] = []
    for name in consumed_inputs:
        if name not in ALLOWED_UPSTREAM_INPUTS:
            failures.append(f"invalid_upstream_input:{name}")
    for name in emitted_outputs:
        if name not in ALLOWED_DOWNSTREAM_OUTPUTS:
            failures.append(f"invalid_downstream_output:{name}")
    for action in claimed_actions:
        if action.startswith(_FORBIDDEN_ACTION_PREFIXES):
            failures.append(f"forbidden_owner_overlap:{action}")
    return sorted(set(failures))


def run_governance_recommendation_engine(*, program_brief: Mapping[str, Any], roadmap_signal_bundle: Mapping[str, Any], evaluation_patterns: list[Mapping[str, Any]], created_at: str, trace_id: str) -> dict[str, Any]:
    unresolved = sorted({str(v) for v in roadmap_signal_bundle.get("missing_eval_coverage", []) if str(v)})
    hotspots = sorted({str(v) for v in roadmap_signal_bundle.get("override_hotspots", []) if str(v)})
    if not unresolved and not hotspots:
        raise PRGHardeningError("governance_inputs_insufficient")

    counts = Counter(str(row.get("pattern_code") or "unknown") for row in evaluation_patterns if isinstance(row, Mapping))
    pattern_rows = [
        {"pattern_code": code, "occurrences": count, "evidence_refs": [f"eval_pattern:{code}"]}
        for code, count in sorted(counts.items())
    ]
    pattern_report = {
        "artifact_type": "evaluation_pattern_report",
        "report_id": f"epr-{_hash([trace_id, created_at, pattern_rows])[:16]}",
        "program_id": str(program_brief.get("program_id") or "PRG-UNKNOWN"),
        "generated_at": created_at,
        "trace_id": trace_id,
        "lineage_ref": str(program_brief.get("lineage_ref") or "lineage:unknown"),
        "patterns": pattern_rows,
        "causal_claims": [
            {
                "claim_id": "claim-1",
                "claim": "recurring coverage gaps increase governance risk",
                "evidence_refs": sorted({*hotspots, *unresolved})[:4],
                "supported": True,
            }
        ],
    }
    validate_artifact(pattern_report, "evaluation_pattern_report")

    adoption_candidates = []
    for code, count in sorted(counts.items()):
        adoption_candidates.append(
            {
                "candidate_id": f"cand-{code}",
                "target_type": "slice_contract",
                "target_ref": f"slice:{code}",
                "priority": min(100, 50 + (count * 10)),
                "reason_codes": ["pattern_recurrence", "trust_gap_first"],
                "authority_scope": "recommendation_only",
                "evidence_refs": [f"evaluation_pattern_report:{pattern_report['report_id']}"],
            }
        )
    candidate_set = {
        "artifact_type": "prioritized_adoption_candidate_set",
        "candidate_set_id": f"pacs-{_hash([trace_id, adoption_candidates])[:16]}",
        "program_id": pattern_report["program_id"],
        "generated_at": created_at,
        "trace_id": trace_id,
        "lineage_ref": pattern_report["lineage_ref"],
        "non_authority_assertions": ["recommendation_only", "not_policy_authority", "not_closure_authority"],
        "candidates": sorted(adoption_candidates, key=lambda row: (-int(row["priority"]), str(row["candidate_id"]))),
    }
    validate_artifact(candidate_set, "prioritized_adoption_candidate_set")

    alignment = {
        "artifact_type": "program_alignment_assessment",
        "assessment_id": f"paa-{_hash([trace_id, unresolved, hotspots])[:16]}",
        "program_id": pattern_report["program_id"],
        "alignment_status": "misaligned" if hotspots else "aligned",
        "strategy_integrity": "trust_gap_first",
        "created_at": created_at,
        "trace_id": trace_id,
        "lineage_ref": pattern_report["lineage_ref"],
        "reason_codes": ["incomplete_trust_layers_prioritized"] if unresolved else ["no_open_trust_gaps"],
        "fail_reasons": ["override_hotspot_detected"] if hotspots else [],
    }
    validate_artifact(alignment, "program_alignment_assessment")

    return {
        "pattern_report": pattern_report,
        "candidate_set": candidate_set,
        "alignment_assessment": alignment,
    }


def run_governance_eval(*, pattern_report: Mapping[str, Any], candidate_set: Mapping[str, Any], alignment_assessment: Mapping[str, Any], evidence_refs: list[str], created_at: str, trace_id: str) -> dict[str, Any]:
    checks = {
        "evidence_sufficient": len([r for r in evidence_refs if str(r).strip()]) >= 2,
        "recommendation_bounded": all(str(c.get("authority_scope")) == "recommendation_only" for c in candidate_set.get("candidates", [])),
        "strategy_alignment": str(alignment_assessment.get("strategy_integrity")) == "trust_gap_first",
        "non_authority_correct": bool(candidate_set.get("non_authority_assertions")),
        "artifact_completeness": bool(pattern_report.get("patterns")) and isinstance(candidate_set.get("candidates"), list),
    }
    fail_reasons = [k for k, ok in checks.items() if not ok]
    result = {
        "artifact_type": "prg_governance_eval_result",
        "eval_id": f"pge-{_hash([trace_id, checks, created_at])[:16]}",
        "created_at": created_at,
        "trace_id": trace_id,
        "lineage_ref": str(pattern_report.get("lineage_ref") or "lineage:unknown"),
        "evaluation_status": "pass" if not fail_reasons else "fail",
        "checks": checks,
        "fail_reasons": sorted(fail_reasons),
    }
    validate_artifact(result, "prg_governance_eval_result")
    return result


def build_governance_readiness(*, eval_result: Mapping[str, Any], evidence_complete: bool, created_at: str, trace_id: str) -> dict[str, Any]:
    fail_reasons = []
    if eval_result.get("evaluation_status") != "pass":
        fail_reasons.append("governance_eval_failed")
    if not evidence_complete:
        fail_reasons.append("governance_evidence_incomplete")
    readiness = {
        "artifact_type": "prg_governance_readiness_record",
        "readiness_id": f"pgr-{_hash([trace_id, eval_result.get('eval_id'), fail_reasons])[:16]}",
        "created_at": created_at,
        "trace_id": trace_id,
        "lineage_ref": str(eval_result.get("lineage_ref") or "lineage:unknown"),
        "readiness_status": "candidate_only" if not fail_reasons else "blocked",
        "non_authority_assertions": [
            "prg_not_policy_authority",
            "prg_not_closure_authority",
            "prg_not_execution_authority",
            "prg_not_runtime_enforcement",
        ],
        "fail_reasons": sorted(fail_reasons),
    }
    validate_artifact(readiness, "prg_governance_readiness_record")
    return readiness


def validate_recommendation_replay(*, prior_inputs: Mapping[str, Any], replay_inputs: Mapping[str, Any], prior_outputs: Mapping[str, Any], replay_outputs: Mapping[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    if _hash(prior_inputs) != _hash(replay_inputs):
        failures.append("replay_input_drift")
    if _hash(prior_outputs) != _hash(replay_outputs):
        failures.append("replay_output_drift")
    return not failures, failures


def check_recommendation_authority_boundary(*, recommendation_artifacts: list[Mapping[str, Any]]) -> list[str]:
    fails: list[str] = []
    for row in recommendation_artifacts:
        purpose = str(row.get("used_for") or "")
        art_id = str(row.get("artifact_id") or "unknown")
        if purpose in {"policy_decision", "closure_decision", "roadmap_progression_authority"}:
            fails.append(f"recommendation_authority_leakage:{art_id}")
    return sorted(set(fails))


def check_adoption_candidate_integrity(*, candidate_set: Mapping[str, Any]) -> list[str]:
    fails: list[str] = []
    for row in candidate_set.get("candidates", []):
        if str(row.get("authority_scope")) != "recommendation_only":
            fails.append(f"candidate_authority_scope_invalid:{row.get('candidate_id')}")
    return sorted(set(fails))


def check_trust_posture_snapshot_integrity(*, trust_posture_snapshot: Mapping[str, Any]) -> list[str]:
    refs = trust_posture_snapshot.get("evidence_refs", [])
    if not isinstance(refs, list) or not refs:
        return ["trust_posture_evidence_missing"]
    if any(str(ref).startswith("narrative:") for ref in refs):
        return ["trust_posture_narrative_inference_blocked"]
    return []


def build_recommendation_rework_debt(*, recommendation_history: list[Mapping[str, Any]], created_at: str, trace_id: str) -> dict[str, Any]:
    counter = Counter(str(r.get("recommendation_key") or "unknown") for r in recommendation_history)
    repeated = {k: c for k, c in counter.items() if c >= 2}
    record = {
        "artifact_type": "prg_recommendation_rework_debt_record",
        "debt_id": f"prd-{_hash([trace_id, repeated, created_at])[:16]}",
        "created_at": created_at,
        "trace_id": trace_id,
        "lineage_ref": "lineage:prg:rework",
        "rework_items": [
            {"recommendation_key": key, "recurrence_count": count, "status": "open"}
            for key, count in sorted(repeated.items())
        ],
        "debt_status": "elevated" if repeated else "stable",
    }
    validate_artifact(record, "prg_recommendation_rework_debt_record")
    return record


def check_governance_to_rdx_integrity(*, prg_handoff: Mapping[str, Any], rdx_input: Mapping[str, Any]) -> list[str]:
    fails = []
    if str(prg_handoff.get("authority_scope")) != "recommendation_only":
        fails.append("handoff_scope_invalid")
    if str(rdx_input.get("authority_scope")) != "recommendation_input":
        fails.append("rdx_input_scope_invalid")
    return sorted(set(fails))


def check_pattern_report_integrity(*, report: Mapping[str, Any]) -> list[str]:
    fails: list[str] = []
    for claim in report.get("causal_claims", []):
        if not claim.get("evidence_refs"):
            fails.append(f"unsupported_causal_claim:{claim.get('claim_id')}")
    return sorted(set(fails))


def run_prg_boundary_redteam(*, fixtures: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    findings = []
    for row in fixtures:
        if row.get("should_fail_closed") and row.get("observed") != "blocked":
            findings.append({"fixture_id": str(row.get("fixture_id")), "severity": "high", "class": "boundary_fail_open"})
    return sorted(findings, key=lambda r: r["fixture_id"])


def run_prg_semantic_redteam(*, fixtures: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    findings = []
    for row in fixtures:
        if row.get("semantic_risk") and row.get("observed") != "blocked":
            findings.append({"fixture_id": str(row.get("fixture_id")), "severity": "high", "class": "semantic_fail_open"})
    return sorted(findings, key=lambda r: r["fixture_id"])


def build_governance_effectiveness(*, outcomes: list[Mapping[str, Any]], created_at: str, trace_id: str) -> dict[str, Any]:
    if not outcomes:
        raise PRGHardeningError("effectiveness_outcomes_required")
    improved = sum(1 for row in outcomes if row.get("trust_improved") is True)
    drift_reduced = sum(1 for row in outcomes if row.get("drift_reduced") is True)
    alignment_improved = sum(1 for row in outcomes if row.get("alignment_improved") is True)
    total = len(outcomes)
    score = round((improved + drift_reduced + alignment_improved) / (total * 3), 4)
    record = {
        "artifact_type": "prg_governance_effectiveness_record",
        "effectiveness_id": f"pgeff-{_hash([trace_id, score, created_at])[:16]}",
        "created_at": created_at,
        "trace_id": trace_id,
        "lineage_ref": "lineage:prg:effectiveness",
        "window_size": total,
        "trust_improvement_rate": round(improved / total, 4),
        "drift_reduction_rate": round(drift_reduced / total, 4),
        "alignment_improvement_rate": round(alignment_improved / total, 4),
        "effectiveness_score": score,
        "value_status": "improving" if score >= 0.66 else "stagnating",
    }
    validate_artifact(record, "prg_governance_effectiveness_record")
    return record


def build_governance_conflict_record(*, conflict_codes: list[str], created_at: str, trace_id: str) -> dict[str, Any]:
    record = {
        "artifact_type": "prg_governance_conflict_record",
        "conflict_id": f"pgc-{_hash([trace_id, conflict_codes, created_at])[:16]}",
        "created_at": created_at,
        "trace_id": trace_id,
        "lineage_ref": "lineage:prg:conflicts",
        "conflict_codes": sorted({str(c) for c in conflict_codes if str(c)}),
        "severity": "high" if conflict_codes else "none",
    }
    validate_artifact(record, "prg_governance_conflict_record")
    return record


def build_governance_bundle(*, artifact_refs: list[str], created_at: str, trace_id: str) -> dict[str, Any]:
    bundle = {
        "artifact_type": "prg_governance_bundle",
        "bundle_id": f"pgb-{_hash([trace_id, artifact_refs, created_at])[:16]}",
        "created_at": created_at,
        "trace_id": trace_id,
        "lineage_ref": "lineage:prg:bundle",
        "artifact_refs": sorted({str(ref) for ref in artifact_refs if str(ref)}),
        "non_authority_assertions": ["recommendation_only", "candidate_only_readiness"],
    }
    validate_artifact(bundle, "prg_governance_bundle")
    return bundle


def run_prg_closeout_gate(*, recommendation_replay_ok: bool, strategy_alignment_ok: bool, authority_boundary_failures: list[str], effectiveness_record: Mapping[str, Any]) -> dict[str, Any]:
    checks = {
        "recommendation_replay_validation": recommendation_replay_ok,
        "strategy_alignment_integrity": strategy_alignment_ok,
        "recommendation_vs_authority_protection": len(authority_boundary_failures) == 0,
        "governance_effectiveness_tracking": bool(effectiveness_record.get("effectiveness_score") is not None),
        "prg_non_authoritative_posture": bool(effectiveness_record.get("artifact_type") == "prg_governance_effectiveness_record"),
    }
    fail_reasons = [k for k, ok in checks.items() if not ok]
    return {
        "closeout_gate": "pass" if not fail_reasons else "fail",
        "checks": checks,
        "fail_reasons": fail_reasons,
    }
