from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any


LEVEL_RANK = {"global_invariant": 0, "domain_policy": 1, "doctrine": 2, "local_override": 3}


def _stable_hash(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _ts(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value).astimezone(timezone.utc)


@dataclass(frozen=True)
class DesiredStateRegistry:
    """Versioned desired-state registry for OPX-142."""

    def register(self, target_id: str, version: str, state: dict[str, Any], source: dict[str, str], generated_at: str) -> dict[str, Any]:
        record = {
            "artifact_type": "rsm_desired_state_registry_entry",
            "target_id": target_id,
            "version": version,
            "state": state,
            "source": source,
            "generated_at": generated_at,
            "freshness_hours": 0.0,
            "non_authoritative": True,
        }
        record["entry_id"] = f"rsm-ds-{_stable_hash(record)}"
        return record

    def retrieve(self, entries: list[dict[str, Any]], target_id: str, version: str | None = None) -> dict[str, Any]:
        candidates = [e for e in entries if e["target_id"] == target_id]
        if version is not None:
            candidates = [e for e in candidates if e["version"] == version]
        if not candidates:
            raise ValueError("desired_state_not_found")
        ordered = sorted(candidates, key=lambda item: item["version"])
        return ordered[-1]


@dataclass(frozen=True)
class OPX005Runtime:
    """Deterministic non-authoritative artifact engine for OPX-005 slices."""

    def precedent_eligibility_gate(self, precedents: list[dict[str, Any]], *, scope: str, now: str) -> dict[str, Any]:
        current = _ts(now)
        eligible: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        for item in precedents:
            reasons: list[str] = []
            if not item.get("active", False):
                reasons.append("inactive")
            if item.get("superseded_by"):
                reasons.append("superseded")
            if item.get("scope") != scope:
                reasons.append("scope_mismatch")
            if not item.get("provenance_valid", False):
                reasons.append("invalid_provenance")
            expiry = item.get("expires_at")
            if expiry and _ts(expiry) < current:
                reasons.append("expired")
            if reasons:
                rejected.append({"precedent_id": item["precedent_id"], "reasons": sorted(reasons)})
            else:
                eligible.append(item)
        return {
            "artifact_type": "ril_precedent_eligibility_artifact",
            "eligible_precedents": sorted(eligible, key=lambda p: p["precedent_id"]),
            "rejected_precedents": sorted(rejected, key=lambda r: r["precedent_id"]),
            "non_authoritative": True,
        }

    def resolve_precedence(self, rules: list[dict[str, Any]]) -> dict[str, Any]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for rule in rules:
            grouped.setdefault(rule["key"], []).append(rule)
        resolved: list[dict[str, Any]] = []
        conflicts: list[dict[str, Any]] = []
        for key, bucket in sorted(grouped.items()):
            ordered = sorted(bucket, key=lambda r: (LEVEL_RANK[r["layer"]], r.get("priority", 100), r["rule_id"]))
            winner = ordered[0]
            values = {r["value"] for r in ordered}
            if len(values) > 1:
                conflicts.append({"key": key, "winner": winner["rule_id"], "conflicted_rule_ids": [r["rule_id"] for r in ordered[1:]]})
            resolved.append({"key": key, "value": winner["value"], "winner_rule_id": winner["rule_id"], "winner_layer": winner["layer"]})
        return {"artifact_type": "precedence_resolution_artifact", "resolved": resolved, "conflicts": conflicts, "non_authoritative": True}

    def compile_judgment_to_policy(self, judgment: dict[str, Any]) -> dict[str, Any]:
        required = ["judgment_id", "scope", "stable_cycles", "validation_passed", "policy_candidate"]
        missing = [key for key in required if key not in judgment]
        if missing or not judgment.get("validation_passed") or judgment.get("stable_cycles", 0) < 2:
            return {
                "artifact_type": "judgment_compilation_result",
                "status": "commentary_only",
                "reason": "validation_gate_failed",
                "missing": missing,
                "non_authoritative": True,
            }
        return {
            "artifact_type": "judgment_compilation_result",
            "status": "policy_candidate",
            "policy_candidate": judgment["policy_candidate"],
            "source_judgment_id": judgment["judgment_id"],
            "non_authoritative": True,
            "auto_apply": False,
        }

    def reconciliation_debt(self, deltas: list[dict[str, Any]]) -> dict[str, Any]:
        per_module: dict[str, float] = {}
        for delta in deltas:
            per_module[delta["module_id"]] = per_module.get(delta["module_id"], 0.0) + float(delta.get("magnitude", 0.0))
        portfolio_score = round(sum(per_module.values()), 4)
        return {
            "artifact_type": "rsm_reconciliation_debt_artifact",
            "module_debt": {k: round(v, 4) for k, v in sorted(per_module.items())},
            "portfolio_debt": portfolio_score,
            "trend": "worsening" if portfolio_score > len(per_module) else "stable",
            "non_authoritative": True,
        }

    def promotion_bundle_completeness(self, bundle: dict[str, Any]) -> dict[str, Any]:
        required = ["replay", "provenance", "evidence", "tests", "risk"]
        present = [key for key in required if bundle.get(key)]
        missing = [key for key in required if key not in present]
        score = round(len(present) / len(required), 4)
        return {
            "artifact_type": "promotion_bundle_completeness_artifact",
            "completeness_score": score,
            "strength": "robust" if score >= 0.8 else "thin",
            "missing_components": missing,
            "non_authoritative": True,
        }

    def verify_promotion_provenance(self, lineage: dict[str, Any]) -> dict[str, Any]:
        checks = {
            "has_lineage": bool(lineage.get("lineage_chain")),
            "has_replay_link": bool(lineage.get("replay_ref")),
            "has_evidence_link": bool(lineage.get("evidence_ref")),
        }
        passed = all(checks.values())
        return {
            "artifact_type": "promotion_provenance_verification_artifact",
            "passed": passed,
            "checks": checks,
            "blocked": not passed,
            "fail_closed": not passed,
        }

    def policy_release_gate(self, lane: dict[str, Any]) -> dict[str, Any]:
        safe = bool(lane.get("tests_passed")) and bool(lane.get("reviewed")) and bool(lane.get("canary_ready"))
        return {
            "artifact_type": "policy_release_readiness_artifact",
            "release_ready": safe,
            "rollback_hook_present": bool(lane.get("rollback_hook")),
            "activation_mode": "blocked" if not safe else "manual_only",
            "non_authoritative": True,
        }

    def dem_decision_economics(self, model: dict[str, float]) -> dict[str, Any]:
        cod = model.get("cost_of_delay", 0.0)
        fp = model.get("false_positive_cost", 0.0)
        fn = model.get("false_negative_cost", 0.0)
        hr = model.get("human_review_cost", 0.0)
        score = round((fn * 1.2 + cod) - (fp * 0.7 + hr * 0.5), 4)
        return {
            "artifact_type": "dem_decision_economics_artifact",
            "cost_of_delay_model": cod,
            "false_positive_cost_model": fp,
            "false_negative_cost_model": fn,
            "human_review_cost_model": hr,
            "economic_decision_score": score,
            "recommendation_only": True,
            "non_authoritative": True,
        }

    def brm_blast_radius(self, request: dict[str, Any]) -> dict[str, Any]:
        impact = int(request.get("affected_modules", 0))
        irreversible = bool(request.get("irreversible", False))
        rollback_difficulty = min(1.0, round((impact / 10.0) + (0.4 if irreversible else 0.0), 4))
        escalation = impact >= 5 or irreversible
        return {
            "artifact_type": "brm_blast_radius_assessment",
            "blast_radius_assessment": "high" if escalation else "low",
            "irreversibility_classification": "irreversible" if irreversible else "reversible",
            "rollback_difficulty_score": rollback_difficulty,
            "escalation_requirement_record": escalation,
            "multi_review_requirement_record": escalation,
            "non_authoritative": True,
        }

    def mcl_compaction(self, records: list[dict[str, Any]], *, active_days: int = 30) -> dict[str, Any]:
        compact: list[str] = []
        archive: list[str] = []
        for item in sorted(records, key=lambda r: r["record_id"]):
            age = int(item.get("age_days", 0))
            if age > active_days:
                archive.append(item["record_id"])
            elif item.get("entropy", 0.0) > 0.8:
                compact.append(item["record_id"])
        return {
            "artifact_type": "mcl_memory_compaction_plan",
            "memory_compaction_plan": compact,
            "archival_tier_assignment": archive,
            "retention_policy_artifact": {"active_days": active_days},
            "memory_entropy_report": {"high_entropy_count": len(compact)},
            "archive_prune_record": {"candidate_count": len(archive)},
            "non_authoritative": True,
        }

    def dcl_compile_doctrine(self, judgments: list[dict[str, Any]]) -> dict[str, Any]:
        stable = [j for j in judgments if j.get("stable", False) and j.get("validated", False)]
        conflicts = sorted({j["topic"] for j in stable if j.get("conflict", False)})
        doctrine = [{"topic": j["topic"], "stance": j["stance"], "source": j["judgment_id"]} for j in sorted(stable, key=lambda s: s["judgment_id"])]
        return {
            "artifact_type": "dcl_doctrine_artifact",
            "doctrine_artifact": doctrine,
            "doctrine_conflict_record": conflicts,
            "doctrine_lineage_record": [d["source"] for d in doctrine],
            "doctrine_update_candidate": bool(doctrine),
            "non_authoritative": True,
        }

    def xrl_weight_outcomes(self, signals: list[dict[str, Any]], *, now: str) -> dict[str, Any]:
        current = _ts(now)
        weighted: list[dict[str, Any]] = []
        for signal in sorted(signals, key=lambda s: s["signal_id"]):
            age_days = max((current - _ts(signal["observed_at"])).days, 0)
            recency = max(0.1, 1.0 - age_days / 365.0)
            corroboration = min(1.0, 0.4 + 0.1 * int(signal.get("corroborations", 0)))
            reputation = float(signal.get("source_reputation", 0.5))
            weight = round(recency * corroboration * reputation, 4)
            weighted.append({**signal, "outcome_trust_weight": weight})
        return {
            "artifact_type": "xrl_external_outcome_impact_artifact",
            "external_outcome_signal": weighted,
            "outcome_normalization_record": {"count": len(weighted)},
            "external_feedback_binding_record": [s["signal_id"] for s in weighted],
            "non_authoritative": True,
        }

    def trace_completeness_gate(self, trace: dict[str, Any]) -> dict[str, Any]:
        critical = ["trace_id", "lineage_chain", "evidence_refs", "replay_ref"]
        missing = [item for item in critical if not trace.get(item)]
        score = round((len(critical) - len(missing)) / len(critical), 4)
        return {
            "artifact_type": "trace_completeness_gate_artifact",
            "completeness_score": score,
            "missing_critical": missing,
            "allow_progression": not missing,
            "fail_closed": bool(missing),
        }

    def readiness_planner(self, modules: list[dict[str, Any]]) -> dict[str, Any]:
        ranked = []
        for item in modules:
            readiness = 0.35 * item.get("trust", 0.0) + 0.25 * item.get("outcome", 0.0) + 0.25 * (1 - item.get("burden", 0.0)) + 0.15 * item.get("compatibility", 0.0)
            ranked.append({"module_id": item["module_id"], "readiness_score": round(readiness, 4)})
        ranked = sorted(ranked, key=lambda r: (-r["readiness_score"], r["module_id"]))
        return {"artifact_type": "portfolio_slice_readiness_artifact", "recommendations": ranked, "non_authoritative": True}

    def strategic_scenarios(self, posture: dict[str, float]) -> dict[str, Any]:
        scenarios = [
            {"scenario_id": "stabilize", "assumption": "reduce burden", "projected_score": round(posture.get("trust", 0.0) * 0.7 + (1 - posture.get("burden", 0.0)) * 0.3, 4)},
            {"scenario_id": "expand", "assumption": "increase capacity", "projected_score": round(posture.get("trust", 0.0) * 0.5 + posture.get("outcome", 0.0) * 0.5, 4)},
        ]
        return {"artifact_type": "strategic_scenario_artifact", "scenarios": scenarios, "non_authoritative": True}

    def redteam_findings(self, round_id: str, attacks: list[dict[str, Any]]) -> dict[str, Any]:
        findings = []
        for attack in attacks:
            exposed = bool(attack.get("exposed", False))
            findings.append({"scenario": attack["scenario"], "severity": "high" if exposed else "contained", "needs_fix": exposed})
        return {
            "artifact_type": "redteam_findings_artifact",
            "round_id": round_id,
            "findings": findings,
            "fix_wave_required": any(f["needs_fix"] for f in findings),
        }

    def fix_wave(self, findings_artifact: dict[str, Any]) -> dict[str, Any]:
        remediated = [f["scenario"] for f in findings_artifact["findings"] if f["needs_fix"]]
        return {
            "artifact_type": "redteam_fix_wave_artifact",
            "round_id": findings_artifact["round_id"],
            "remediated_scenarios": remediated,
            "remaining_open": [],
            "status": "resolved" if remediated or not findings_artifact.get("fix_wave_required") else "pending",
        }
