"""NX governed intelligence runtime extensions.

This module provides deterministic, fail-closed, non-authoritative preparatory and
recommendation capabilities that can be consumed by canonical authority seams.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from statistics import median
from typing import Any


class NXGovernedIntelligenceError(ValueError):
    """Raised when deterministic governed intelligence processing fails."""


def _stable_sort(items: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda row: tuple(str(row.get(k, "")) for k in keys))


def build_artifact_intelligence_index(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = _stable_sort(artifacts, ("artifact_id", "artifact_type", "created_at"))
    return {
        "artifact_type": {},
        "schema_version": {},
        "trace_id": {},
        "span_id": {},
        "run_id": {},
        "policy_version": {},
        "decision_outcome": {},
        "reason_codes": {},
        "blocker_class": {},
        "eval_slice": {},
        "route_version": {},
        "prompt_version": {},
        "time_window": {},
        "records": ordered,
    } | _index_dimensions(ordered)


def _index_dimensions(ordered: list[dict[str, Any]]) -> dict[str, dict[str, list[str]]]:
    index: dict[str, dict[str, list[str]]] = {
        "artifact_type": {},
        "schema_version": {},
        "trace_id": {},
        "span_id": {},
        "run_id": {},
        "policy_version": {},
        "decision_outcome": {},
        "reason_codes": {},
        "blocker_class": {},
        "eval_slice": {},
        "route_version": {},
        "prompt_version": {},
        "time_window": {},
    }
    for row in ordered:
        artifact_id = str(row.get("artifact_id", ""))
        if not artifact_id:
            raise NXGovernedIntelligenceError("artifact_id required for indexing")
        for field in (
            "artifact_type",
            "schema_version",
            "trace_id",
            "span_id",
            "run_id",
            "policy_version",
            "decision_outcome",
            "blocker_class",
            "eval_slice",
            "route_version",
            "prompt_version",
            "time_window",
        ):
            value = str(row.get(field, ""))
            if value:
                index[field].setdefault(value, []).append(artifact_id)
        for reason in sorted(str(x) for x in row.get("reason_codes", []) if str(x)):
            index["reason_codes"].setdefault(reason, []).append(artifact_id)

    for dim in index:
        for key in list(index[dim].keys()):
            index[dim][key] = sorted(set(index[dim][key]))
    return index


def query_top_blocker_families(index: dict[str, Any], top_k: int = 5) -> list[dict[str, Any]]:
    counts = [
        {"blocker_class": blocker, "count": len(ids)}
        for blocker, ids in sorted(index.get("blocker_class", {}).items())
    ]
    return sorted(counts, key=lambda row: (-int(row["count"]), row["blocker_class"]))[:top_k]


def query_recurring_failure_motifs(index: dict[str, Any], minimum_count: int = 2) -> list[dict[str, Any]]:
    records = index.get("records", [])
    motif_counter: Counter[tuple[str, str]] = Counter()
    for row in records:
        if str(row.get("decision_outcome", "")) not in {"failed", "blocked"}:
            continue
        motif_counter[(str(row.get("blocker_class", "")), str(row.get("eval_slice", "")))] += 1
    motifs = [
        {"blocker_class": blocker, "eval_slice": slc, "count": count}
        for (blocker, slc), count in motif_counter.items()
        if count >= minimum_count
    ]
    return sorted(motifs, key=lambda row: (-int(row["count"]), row["blocker_class"], row["eval_slice"]))


def query_policy_conflict_surfaces(index: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [x for x in index.get("records", []) if "policy_conflict" in {str(r) for r in x.get("reason_codes", [])}]
    grouped: dict[tuple[str, str], int] = {}
    for row in rows:
        key = (str(row.get("policy_version", "unknown")), str(row.get("route_version", "unknown")))
        grouped[key] = grouped.get(key, 0) + 1
    return [
        {"policy_version": k[0], "route_version": k[1], "conflict_count": v}
        for k, v in sorted(grouped.items(), key=lambda item: (-item[1], item[0][0], item[0][1]))
    ]


def query_override_hotspots(index: dict[str, Any]) -> list[dict[str, Any]]:
    by_trace: Counter[str] = Counter()
    for row in index.get("records", []):
        if "override" in {str(r) for r in row.get("reason_codes", [])}:
            by_trace[str(row.get("trace_id", "unknown"))] += 1
    return [
        {"trace_id": trace, "override_count": count}
        for trace, count in sorted(by_trace.items(), key=lambda item: (-item[1], item[0]))
    ]


def query_stale_artifact_attempts(index: dict[str, Any]) -> list[dict[str, Any]]:
    stale = []
    for row in index.get("records", []):
        reasons = {str(x) for x in row.get("reason_codes", [])}
        if "stale_artifact" in reasons:
            stale.append({"artifact_id": row["artifact_id"], "run_id": row.get("run_id"), "trace_id": row.get("trace_id")})
    return _stable_sort(stale, ("artifact_id", "run_id", "trace_id"))


def query_promotion_guard_blocks(index: dict[str, Any]) -> list[dict[str, Any]]:
    blocked = [r for r in index.get("records", []) if str(r.get("decision_outcome", "")) == "promotion_blocked"]
    return _stable_sort(
        [{"artifact_id": r["artifact_id"], "policy_version": r.get("policy_version"), "blocker_class": r.get("blocker_class")} for r in blocked],
        ("artifact_id", "policy_version", "blocker_class"),
    )


def build_artifact_intelligence_report(index: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_type": "artifact_intelligence_report",
        "authority_scope": "non_authoritative",
        "top_blockers": query_top_blocker_families(index),
        "recurring_failure_motifs": query_recurring_failure_motifs(index),
        "policy_conflict_surfaces": query_policy_conflict_surfaces(index),
        "override_hotspots": query_override_hotspots(index),
        "stale_artifact_attempts": query_stale_artifact_attempts(index),
        "promotion_guard_blocks": query_promotion_guard_blocks(index),
    }


def build_judgment_record(payload: dict[str, Any]) -> dict[str, Any]:
    required = [
        "question_under_judgment",
        "candidate_outcomes",
        "selected_outcome",
        "evidence_refs",
        "claims_considered",
        "rules_applied",
        "assumptions",
        "alternatives_considered",
        "uncertainties",
        "decision_change_conditions",
        "rationale_summary",
    ]
    missing = [k for k in required if k not in payload]
    if missing:
        raise NXGovernedIntelligenceError(f"judgment record missing required fields: {','.join(missing)}")
    return {
        "artifact_type": "judgment_record",
        "authority_scope": "non_authoritative",
        "precedent_refs": sorted(set(str(x) for x in payload.get("precedent_refs", []))),
        **payload,
    }


def run_judgment_eval_suite(judgment_record: dict[str, Any], *, prior_selected_outcome: str | None = None) -> dict[str, Any]:
    evidence_coverage = bool(judgment_record.get("evidence_refs"))
    contradiction_detected = judgment_record.get("selected_outcome") in set(judgment_record.get("alternatives_considered", []))
    policy_alignment = bool(judgment_record.get("rules_applied"))
    uncertainty_calibration = len(judgment_record.get("uncertainties", [])) > 0
    replay_consistency = prior_selected_outcome in {None, judgment_record.get("selected_outcome")}
    longitudinal_calibration = prior_selected_outcome is not None

    evals = {
        "evidence_coverage": evidence_coverage,
        "contradiction_detection": not contradiction_detected,
        "policy_alignment": policy_alignment,
        "uncertainty_calibration": uncertainty_calibration,
        "replay_consistency": replay_consistency,
        "longitudinal_calibration": longitudinal_calibration,
    }
    return {
        "artifact_type": "judgment_eval_summary",
        "authority_scope": "non_authoritative",
        "results": evals,
        "all_required_passed": all(evals.values()),
    }


def require_judgment_eval_pass(summary: dict[str, Any], required: list[str]) -> None:
    failed = [name for name in required if not bool(summary.get("results", {}).get(name, False))]
    if failed:
        raise NXGovernedIntelligenceError(f"required judgment evals failed or missing: {','.join(sorted(failed))}")


_POLICY_STATES = {"draft", "canary", "active", "deprecated", "revoked"}
_POLICY_ALLOWED = {
    "draft": {"canary", "revoked"},
    "canary": {"active", "deprecated", "revoked"},
    "active": {"deprecated", "revoked"},
    "deprecated": {"revoked"},
    "revoked": set(),
}


@dataclass
class JudgmentPolicyRegistry:
    policies: dict[str, dict[str, Any]] = field(default_factory=dict)

    def register_policy(self, policy: dict[str, Any]) -> dict[str, Any]:
        policy_id = str(policy.get("policy_id", ""))
        version = str(policy.get("version", ""))
        if not policy_id or not version:
            raise NXGovernedIntelligenceError("policy_id and version are required")
        state = str(policy.get("state", "draft"))
        if state not in _POLICY_STATES:
            raise NXGovernedIntelligenceError(f"invalid policy state: {state}")
        key = f"{policy_id}@{version}"
        stored = {
            "authority_scope": "non_authoritative",
            "required_inputs": sorted(set(str(x) for x in policy.get("required_inputs", []))),
            **policy,
            "state": state,
        }
        self.policies[key] = stored
        return stored

    def transition(self, policy_id: str, version: str, target_state: str) -> dict[str, Any]:
        key = f"{policy_id}@{version}"
        if key not in self.policies:
            raise NXGovernedIntelligenceError(f"unknown policy: {key}")
        current = str(self.policies[key]["state"])
        if target_state not in _POLICY_ALLOWED[current]:
            raise NXGovernedIntelligenceError(f"illegal transition {current}->{target_state}")
        self.policies[key]["state"] = target_state
        return self.policies[key]

    def build_application_request(self, policy_id: str, version: str) -> dict[str, Any]:
        key = f"{policy_id}@{version}"
        if key not in self.policies:
            raise NXGovernedIntelligenceError(f"unknown policy: {key}")
        policy = self.policies[key]
        return {
            "artifact_type": "judgment_policy_application_request",
            "authority_scope": "non_authoritative",
            "policy_ref": key,
            "state": policy["state"],
            "requires_tpa_authority": True,
        }


def retrieve_precedents(*, query: str, records: list[dict[str, Any]], method: str, method_version: str, top_k: int, threshold: float) -> dict[str, Any]:
    query_terms = set(query.lower().split())
    scored: list[dict[str, Any]] = []
    for row in sorted(records, key=lambda r: str(r.get("record_id", ""))):
        text = f"{row.get('question_under_judgment', '')} {row.get('rationale_summary', '')}".lower()
        tokens = set(text.split())
        if not query_terms:
            score = 0.0
        else:
            score = len(query_terms & tokens) / len(query_terms)
        if score >= threshold:
            scored.append({"record_id": row.get("record_id"), "score": round(score, 6)})

    selected = sorted(scored, key=lambda r: (-float(r["score"]), str(r["record_id"])))[:top_k]
    return {
        "artifact_type": "precedent_retrieval_record",
        "authority_scope": "non_authoritative",
        "method": method,
        "method_version": method_version,
        "inputs": {"query": query},
        "top_k": top_k,
        "threshold": threshold,
        "selected_scores": selected,
    }


def fuse_signals(signals: dict[str, Any]) -> dict[str, Any]:
    required = {"preflight", "eval_summary", "runtime_observability", "judgment_eval", "replay_drift", "certification_state"}
    missing = sorted(required - set(signals.keys()))
    if missing:
        raise NXGovernedIntelligenceError(f"missing signal groups: {','.join(missing)}")
    return {
        "artifact_type": "fused_signal_record",
        "authority_scope": "preparatory_non_authoritative",
        "signals": signals,
        "prepared_for": ["cde_decision_input", "tpa_gating_input"],
    }


def aggregate_multi_run(runs: list[dict[str, Any]]) -> dict[str, Any]:
    if not runs:
        raise NXGovernedIntelligenceError("at least one run is required")
    latency = sorted(float(r.get("latency_ms", 0.0)) for r in runs)
    return {
        "artifact_type": "multi_run_aggregate",
        "authority_scope": "non_authoritative",
        "run_count": len(runs),
        "pass_frequency": sum(1 for r in runs if r.get("status") == "pass") / len(runs),
        "repair_outcomes": dict(Counter(str(r.get("repair_outcome", "unknown")) for r in runs)),
        "blocker_class_rates": dict(Counter(str(r.get("blocker_class", "none")) for r in runs)),
        "latency_distribution_ms": {
            "min": latency[0],
            "median": median(latency),
            "max": latency[-1],
        },
        "drift_frequency": sum(1 for r in runs if bool(r.get("drift_detected"))) / len(runs),
        "promotion_guard_block_rate": sum(1 for r in runs if bool(r.get("promotion_blocked"))) / len(runs),
    }


def mine_patterns(events: list[dict[str, Any]]) -> dict[str, Any]:
    motif_counts = Counter((str(e.get("category", "")), str(e.get("motif", ""))) for e in events)
    recurring = [
        {"category": c, "motif": m, "count": n}
        for (c, m), n in motif_counts.items()
        if n > 1
    ]
    recurring = sorted(recurring, key=lambda r: (-int(r["count"]), r["category"], r["motif"]))
    return {
        "artifact_type": "pattern_mining_recommendation",
        "authority_scope": "recommendation_only",
        "recurring_motifs": recurring,
        "improvement_candidates": [f"candidate:{row['category']}:{row['motif']}" for row in recurring],
    }


def validate_cross_system_consistency(signals: list[dict[str, Any]]) -> dict[str, Any]:
    divergences: list[dict[str, Any]] = []
    keys = ["policy_version", "judgment_outcome", "certification_status", "promotion_path", "replay_outcome"]
    for key in keys:
        values = sorted({str(s.get(key, "")) for s in signals})
        if len(values) > 1:
            divergences.append({"dimension": key, "observed_values": values})
    return {
        "artifact_type": "cross_system_inconsistency_record",
        "authority_scope": "non_authoritative_detection",
        "divergence_detected": bool(divergences),
        "divergences": divergences,
    }


def evolve_policy_candidates(*, pattern_report: dict[str, Any], overrides: list[dict[str, Any]], precedents: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = []
    for idx, motif in enumerate(pattern_report.get("recurring_motifs", []), start=1):
        candidates.append({
            "candidate_id": f"policy-candidate-{idx:03d}",
            "source": "pattern",
            "motif": motif,
            "state": "draft",
            "authority_scope": "non_authoritative",
        })
    if overrides:
        candidates.append({"candidate_id": "threshold-candidate-001", "source": "override_hotspot", "state": "draft", "authority_scope": "non_authoritative"})
    if precedents:
        candidates.append({"candidate_id": "contract-candidate-001", "source": "stable_precedent", "state": "draft", "authority_scope": "non_authoritative"})
    return {"artifact_type": "policy_evolution_candidate_set", "authority_scope": "recommendation_only", "candidates": candidates}


def simulate_scenarios(changes: list[dict[str, Any]]) -> dict[str, Any]:
    projections = []
    for change in sorted(changes, key=lambda row: (str(row.get("change_type", "")), str(row.get("change_id", "")))):
        impact_score = round(float(change.get("magnitude", 0.0)) * float(change.get("confidence", 1.0)), 6)
        projections.append({"change_id": change.get("change_id"), "change_type": change.get("change_type"), "projected_impact_score": impact_score})
    return {
        "artifact_type": "scenario_simulation_result",
        "authority_scope": "simulation_non_authoritative",
        "projected_outcomes": projections,
        "requires_authority_consumer": True,
    }


def build_explainability_artifact(linkage: dict[str, Any]) -> dict[str, Any]:
    required = ["trace", "input_artifacts", "eval_results", "judgment_records", "policy_refs", "control_decisions", "enforcement_actions"]
    missing = [k for k in required if k not in linkage]
    if missing:
        raise NXGovernedIntelligenceError(f"missing explainability linkage fields: {','.join(missing)}")
    return {
        "artifact_type": "decision_explainability_artifact",
        "authority_scope": "non_authoritative",
        "machine_readable": linkage,
        "human_readable_summary": " -> ".join([str(linkage["trace"]), str(linkage["control_decisions"]), str(linkage["enforcement_actions"])]),
    }


def compute_trust_score(inputs: dict[str, float | bool]) -> dict[str, Any]:
    score = (
        float(inputs.get("eval_pass_rate", 0.0)) * 0.3
        + float(inputs.get("replay_consistency", 0.0)) * 0.2
        + (1.0 - float(inputs.get("drift", 0.0))) * 0.15
        + float(inputs.get("judgment_calibration", 0.0)) * 0.15
        + float(inputs.get("certification", 0.0)) * 0.1
        + (1.0 - float(inputs.get("blocker_trend", 0.0))) * 0.1
    )
    return {
        "artifact_type": "system_trust_score_artifact",
        "authority_scope": "recommendation_only",
        "trust_score": round(score, 6),
    }


def build_feedback_flywheel_artifacts(*, failure: dict[str, Any], eval_summary: dict[str, Any], pattern_report: dict[str, Any], policy_candidates: dict[str, Any], activation_outcome: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_type": "feedback_flywheel_record",
        "authority_scope": "non_authoritative",
        "chain": {
            "failure_to_eval": {"failure_id": failure.get("failure_id"), "eval_id": eval_summary.get("artifact_type")},
            "eval_to_pattern": {"eval": eval_summary.get("artifact_type"), "pattern": pattern_report.get("artifact_type")},
            "pattern_to_candidate": {"pattern": pattern_report.get("artifact_type"), "candidate": policy_candidates.get("artifact_type")},
            "candidate_to_activation": {"candidate_state": [c.get("state") for c in policy_candidates.get("candidates", [])], "activation": activation_outcome},
        },
    }


@dataclass
class PromptTaskRouteRegistry:
    tasks: dict[str, dict[str, Any]] = field(default_factory=dict)
    prompts: dict[str, dict[str, Any]] = field(default_factory=dict)
    routes: dict[str, dict[str, Any]] = field(default_factory=dict)

    def register_task(self, task_id: str, version: str, metadata: dict[str, Any]) -> None:
        self.tasks[f"{task_id}@{version}"] = {"task_id": task_id, "version": version, **metadata}

    def register_prompt(self, prompt_id: str, version: str, metadata: dict[str, Any]) -> None:
        self.prompts[f"{prompt_id}@{version}"] = {"prompt_id": prompt_id, "version": version, **metadata}

    def register_route(self, route_id: str, version: str, metadata: dict[str, Any]) -> None:
        self.routes[f"{route_id}@{version}"] = {"route_id": route_id, "version": version, **metadata}

    def resolve(self, *, task_ref: str, prompt_ref: str, route_ref: str) -> dict[str, Any]:
        if task_ref not in self.tasks or prompt_ref not in self.prompts or route_ref not in self.routes:
            raise NXGovernedIntelligenceError("registry lookup failed: task/prompt/route entry missing")
        return {
            "task": self.tasks[task_ref],
            "prompt": self.prompts[prompt_ref],
            "route": self.routes[route_ref],
        }


def run_advanced_certification_gate(evidence: dict[str, Any]) -> dict[str, Any]:
    required = [
        "backward_compatibility",
        "replay_integrity",
        "failure_injection",
        "cost_latency_guard",
        "control_loop_enforcement",
        "stateless_isolation",
    ]
    missing = [k for k in required if k not in evidence]
    failing = [k for k in required if k in evidence and not bool(evidence[k])]
    blocked = bool(missing or failing)
    return {
        "artifact_type": "advanced_certification_gate_result",
        "blocked": blocked,
        "missing_evidence": sorted(missing),
        "failing_evidence": sorted(failing),
        "freeze_required": blocked,
    }


def evaluate_autonomy_expansion_gate(*, readiness: dict[str, Any], authority_inputs: dict[str, Any]) -> dict[str, Any]:
    recommendation_only = bool(readiness.get("recommendation_only", True))
    cde_authorized = bool(authority_inputs.get("cde_authorized", False))
    eligible = bool(readiness.get("eligible", False)) and cde_authorized and not recommendation_only
    return {
        "artifact_type": "autonomy_expansion_gate_result",
        "eligible": eligible,
        "blocked_reasons": sorted(
            [
                reason
                for reason, present in {
                    "recommendation_artifact_not_authority": recommendation_only,
                    "missing_cde_authority": not cde_authorized,
                    "readiness_not_eligible": not bool(readiness.get("eligible", False)),
                }.items()
                if present
            ]
        ),
    }
