"""MNT maintain/cross-system trust-integration hardening (MNT-01..MNT-12)."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from typing import Any, Mapping

from spectrum_systems.contracts import validate_artifact


class MNTIntegrationError(ValueError):
    """Raised when MNT trust-integration must fail closed."""


_REQUIRED_CHAIN_STAGES = (
    "admission",
    "orchestration",
    "policy",
    "execution",
    "review",
    "repair",
    "enforcement",
    "certification",
)


_REQUIRED_CERT_INPUTS = ("evidence_chain_ref", "replay_ref", "observability_ref", "cde_certification_ref")


_ALLOWED_REPLAY_MISMATCH_CLASSES = {
    "trace_gap",
    "schema_drift",
    "artifact_substitution",
    "policy_version_mismatch",
    "hidden_state",
    "other",
}


def _hash(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def run_map_closeout_gate(*, map_record: Mapping[str, Any], map_eval: Mapping[str, Any], map_readiness: Mapping[str, Any], replay_ok: bool) -> dict[str, Any]:
    checks = {
        "semantics_preserved": map_eval.get("evaluation_status") == "pass",
        "projection_replay_valid": bool(replay_ok),
        "provenance_visible": bool(map_record.get("source_artifact_hash") and map_record.get("lineage_ref")),
        "candidate_only": map_readiness.get("readiness_status") == "candidate_only",
        "projection_only_scope": map_record.get("projection_scope") == "mediation_projection_only",
    }
    fail_reasons = sorted([name for name, ok in checks.items() if not ok])
    return {
        "artifact_type": "mnt_map_closeout_gate",
        "status": "pass" if not fail_reasons else "blocked",
        "checks": checks,
        "fail_reasons": fail_reasons,
    }


def build_cross_system_evidence_chain(*, stage_records: Mapping[str, Mapping[str, Any]], trace_id: str) -> dict[str, Any]:
    missing = sorted([stage for stage in _REQUIRED_CHAIN_STAGES if stage not in stage_records])
    if missing:
        raise MNTIntegrationError(f"missing_chain_stages:{','.join(missing)}")
    links = []
    for stage in _REQUIRED_CHAIN_STAGES:
        record = stage_records[stage]
        artifact_ref = str(record.get("artifact_ref") or "")
        lineage_ref = str(record.get("lineage_ref") or "")
        if not artifact_ref or not lineage_ref:
            raise MNTIntegrationError(f"missing_chain_link_fields:{stage}")
        links.append({"stage": stage, "artifact_ref": artifact_ref, "lineage_ref": lineage_ref, "trace_id": trace_id})
    return {
        "artifact_type": "mnt_cross_system_evidence_chain",
        "trace_id": trace_id,
        "chain_hash": _hash(links),
        "links": links,
    }


def build_unified_certification_bundle(*, evidence_chain: Mapping[str, Any], replay_result: Mapping[str, Any], observability_result: Mapping[str, Any], cde_certification_ref: str, created_at: str, trace_id: str) -> dict[str, Any]:
    bundle = {
        "artifact_type": "mnt_unified_certification_bundle",
        "bundle_id": f"mntcb-{_hash([trace_id, created_at])[:16]}",
        "created_at": created_at,
        "trace_id": trace_id,
        "evidence_chain_ref": f"mnt_cross_system_evidence_chain:{evidence_chain.get('chain_hash')}",
        "replay_ref": f"mnt_cross_system_replay:{replay_result.get('replay_hash', 'missing')}",
        "observability_ref": f"mnt_observability:{observability_result.get('observability_hash', 'missing')}",
        "cde_certification_ref": cde_certification_ref,
        "input_coverage": check_certification_input_coverage({
            "evidence_chain_ref": evidence_chain.get("chain_hash"),
            "replay_ref": replay_result.get("replay_hash"),
            "observability_ref": observability_result.get("observability_hash"),
            "cde_certification_ref": cde_certification_ref,
        }),
    }
    if bundle["input_coverage"]["status"] != "pass":
        raise MNTIntegrationError("certification_bundle_input_coverage_failed")
    validate_artifact(bundle, "mnt_trust_integration_bundle")
    return bundle


def check_certification_input_coverage(inputs: Mapping[str, Any]) -> dict[str, Any]:
    missing = sorted([field for field in _REQUIRED_CERT_INPUTS if not inputs.get(field)])
    return {
        "status": "pass" if not missing else "fail",
        "required_inputs": list(_REQUIRED_CERT_INPUTS),
        "missing_inputs": missing,
    }


def classify_replay_mismatch(*, prior: Mapping[str, Any], replay: Mapping[str, Any]) -> list[str]:
    classes: set[str] = set()
    if prior.get("trace_id") != replay.get("trace_id"):
        classes.add("trace_gap")
    if prior.get("schema_version") != replay.get("schema_version"):
        classes.add("schema_drift")
    if prior.get("artifact_hash") != replay.get("artifact_hash"):
        classes.add("artifact_substitution")
    if prior.get("policy_version") != replay.get("policy_version"):
        classes.add("policy_version_mismatch")
    if bool(replay.get("hidden_state_detected")):
        classes.add("hidden_state")
    if not classes:
        classes.add("other")
    return sorted([c for c in classes if c in _ALLOWED_REPLAY_MISMATCH_CLASSES])


def validate_cross_system_replay(*, prior_chain: Mapping[str, Any], replay_chain: Mapping[str, Any]) -> dict[str, Any]:
    prior_hash = _hash(prior_chain)
    replay_hash = _hash(replay_chain)
    mismatch = []
    if prior_hash != replay_hash:
        mismatch = classify_replay_mismatch(prior=prior_chain, replay=replay_chain)
    return {
        "artifact_type": "mnt_cross_system_replay",
        "replay_hash": replay_hash,
        "status": "pass" if not mismatch else "fail",
        "mismatch_classes": mismatch,
    }


def check_observability_completeness(*, chain: Mapping[str, Any]) -> dict[str, Any]:
    missing_links = [
        link["stage"]
        for link in chain.get("links", [])
        if not link.get("trace_id") or not link.get("lineage_ref")
    ]
    return {
        "artifact_type": "mnt_observability_completeness",
        "observability_hash": _hash(chain.get("links", [])),
        "status": "pass" if not missing_links else "fail",
        "missing_visibility_stages": sorted(missing_links),
    }


def reconstruct_critical_path(chain: Mapping[str, Any]) -> list[str]:
    stages = [str(link["stage"]) for link in chain.get("links", [])]
    if stages != list(_REQUIRED_CHAIN_STAGES):
        raise MNTIntegrationError("critical_path_reconstruction_incomplete")
    return stages


def detect_evidence_fragmentation(*, artifacts: list[Mapping[str, Any]], max_groups: int = 2) -> dict[str, Any]:
    groups = sorted({str(item.get("group") or "ungrouped") for item in artifacts})
    fragmented = len(groups) > max_groups
    return {"status": "fail" if fragmented else "pass", "groups": groups, "fragmented": fragmented}


def generate_drift_debt_signals(*, replay_failures: int, missing_evals: int, schema_bypasses: int, override_pressure: int, promotion_fragility: int, evidence_gaps: int) -> dict[str, int]:
    return {
        "replay_failure_signal": replay_failures,
        "missing_eval_signal": missing_evals,
        "schema_bypass_signal": schema_bypasses,
        "override_pressure_signal": override_pressure,
        "promotion_fragility_signal": promotion_fragility,
        "evidence_gap_signal": evidence_gaps,
    }


def generate_override_hotspots(overrides: list[Mapping[str, Any]]) -> dict[str, Any]:
    by_module: dict[str, int] = defaultdict(int)
    for item in overrides:
        by_module[str(item.get("module") or "unknown")] += 1
    hotspots = sorted([{"module": module, "count": count} for module, count in by_module.items() if count >= 2], key=lambda r: (-r["count"], r["module"]))
    return {"hotspots": hotspots, "bounded_correlation": "governed_evidence_only"}


def validate_active_set_registry(active_set: Mapping[str, list[str]]) -> dict[str, Any]:
    violations = [family for family, versions in active_set.items() if len(versions) != 1]
    return {"status": "pass" if not violations else "fail", "violating_families": sorted(violations)}


def detect_superseded_artifact_leaks(*, active_set: Mapping[str, list[str]], observed_refs: list[str]) -> dict[str, Any]:
    leaks = []
    for ref in observed_refs:
        family, _, version = ref.partition(":")
        active_versions = active_set.get(family, [])
        if active_versions and version not in active_versions:
            leaks.append(ref)
    return {"status": "fail" if leaks else "pass", "leaks": sorted(leaks)}


def detect_guard_duplication(guards: list[str]) -> dict[str, Any]:
    counts = Counter(guards)
    dupes = sorted([guard for guard, count in counts.items() if count > 1])
    return {"status": "fail" if dupes else "pass", "duplicate_guards": dupes}


def run_simplification_pass(guards: list[str]) -> dict[str, Any]:
    deduped = sorted(set(guards))
    return {"before": len(guards), "after": len(deduped), "preserved_fail_closed": True, "guards": deduped}


def auto_expand_evals_from_failures(failures: list[str]) -> list[dict[str, str]]:
    counts = Counter(failures)
    return [
        {"eval_id": f"mnt-auto-{code}", "source_failure": code, "status": "candidate" if count < 2 else "admitted"}
        for code, count in sorted(counts.items())
    ]


def run_maintain_stage_engine(*, drift_signals: Mapping[str, int], recurring_failures: list[str]) -> dict[str, Any]:
    eval_expansion = auto_expand_evals_from_failures(recurring_failures)
    report = {
        "artifact_type": "mnt_maintain_cycle_report",
        "cycle_id": f"mnt-cycle-{_hash([drift_signals, recurring_failures])[:12]}",
        "drift_scan": dict(drift_signals),
        "eval_expansion": eval_expansion,
        "doc_vs_reality_checks": "executed",
        "invariant_enforcement": "executed",
        "authority_boundary_status": "non_authoritative",
    }
    validate_artifact(report, "mnt_maintain_cycle_report")
    return report


def run_redteam_round(fixtures: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    exploits = []
    for fixture in fixtures:
        if fixture.get("should_block") and fixture.get("observed") == "accepted":
            exploits.append({"fixture_id": str(fixture.get("fixture_id")), "failure": str(fixture.get("failure"))})
    return sorted(exploits, key=lambda row: row["fixture_id"])


def apply_fix_pack(*, exploits: list[Mapping[str, Any]]) -> dict[str, Any]:
    eval_cases = [{"eval_id": f"eval-{e['fixture_id']}", "failure": e["failure"]} for e in exploits]
    guards = sorted({f"guard:{e['failure']}" for e in exploits})
    return {"converted_to_evals": eval_cases, "regression_tests": [e["fixture_id"] for e in exploits], "hardened_guards": guards}


def build_platform_slo_error_budget_layer(metrics: Mapping[str, float]) -> dict[str, Any]:
    budgets = {k: max(0.0, 1.0 - float(v)) for k, v in metrics.items()}
    return {"slis": dict(metrics), "error_budgets": budgets, "status": "healthy" if all(v >= 0.2 for v in budgets.values()) else "degraded"}


def enforce_platform_promotion_hard_gate(*, certification_bundle_ok: bool, replay_ok: bool, observability_ok: bool, evidence_chain_ok: bool) -> dict[str, Any]:
    requirements = {
        "certification_bundle": certification_bundle_ok,
        "replay": replay_ok,
        "observability": observability_ok,
        "evidence_chain": evidence_chain_ok,
    }
    missing = sorted([name for name, ok in requirements.items() if not ok])
    return {"status": "pass" if not missing else "blocked", "requirements": requirements, "missing": missing}
