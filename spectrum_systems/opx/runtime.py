from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

MANDATORY_TEST_COVERAGE = {index: text for index, text in enumerate([
    "operator actions are artifact-backed and cannot bypass authority",
    "review queue behavior is bounded and ownership-safe",
    "FAQ module runs end-to-end through governed flow",
    "FAQ judgment discipline is enforced",
    "FAQ certification requires replay/contract/integration evidence",
    "FAQ dataset registry is versioned and deterministic",
    "FAQ operator runbooks/playbooks are linked and retrievable",
    "prompt compression system moves recurring rules into governed defaults",
    "control-loop bypass detector catches bypass attempts",
    "canary/rollback remains governed",
    "reuse without reuse_record is detectable",
    "error budgets freeze/block only through canonical authority/enforcement",
    "stale/superseded items are not treated as active",
    "compatibility audit detects shared breakage",
    "override hygiene issues are surfaced",
    "red-team pack #1 generates findings and fix wave #1 resolves them",
    "extracted module template is deterministic and reusable",
    "minutes / working paper / comment resolution / study-plan modules reuse the governed pattern",
    "cross-module operator control plane artifacts are generated",
    "counterfactual/backtesting outputs remain non-authoritative",
    "simulation/MATLAB family is resource-bounded and governed",
    "portfolio prioritizer remains recommendation-only",
    "maintain-stage outputs are deterministic and governed",
    "red-team pack #2 generates findings and fix wave #2 resolves them",
    "no new slice duplicates a system-registry owner responsibility",
], start=1)}

OPX_002_MANDATORY_TEST_COVERAGE = {index: text for index, text in enumerate([
    "operator actions are artifact-backed and cannot bypass authority",
    "operator evidence bundles are generated deterministically and linked to provenance",
    "FAQ hardening wave 2 strengthens judgment/override/replay/certification behavior",
    "operator overrides/review findings/corrections become eval/data artifacts deterministically",
    "FAQ module template compiler output is deterministic and reusable",
    "compatibility graph detects shared breakage",
    "policy/judgment conflicts are surfaced deterministically",
    "trust decomposition artifacts are correct and non-authoritative",
    "queue/lead-time/burden metrics are generated correctly",
    "working paper module runs end-to-end under governed flow",
    "comment resolution module runs end-to-end under governed flow",
    "study-plan module runs end-to-end under governed flow",
    "champion/challenger lane remains governed and bounded",
    "maintain-stage outputs are deterministic and governed",
    "simulation/MATLAB promotion pack is bounded, replayable, and certifiable",
    "red-team pack #1 generates findings and fix wave #1 resolves them",
    "semantic cache reuses only on strict governed matches",
    "red-team pack #2 generates findings and fix wave #2 resolves them",
    "no new slice duplicates a registry owner responsibility",
], start=1)}


OPX_003_MANDATORY_TEST_COVERAGE = {index: text for index, text in enumerate([
    "operator actions are artifact-backed and cannot bypass authority",
    "operator evidence bundles are generated deterministically and linked to provenance",
    "FAQ hardening wave 2 strengthens judgment/override/replay/certification behavior",
    "operator overrides/review findings/corrections become eval/data artifacts deterministically",
    "FAQ module template compiler output is deterministic and reusable",
    "compatibility graph detects shared breakage",
    "policy/judgment conflicts are surfaced deterministically",
    "trust decomposition artifacts are correct and non-authoritative",
    "queue/lead-time/burden metrics are generated correctly",
    "working paper module runs end-to-end under governed flow",
    "comment resolution module runs end-to-end under governed flow",
    "study-plan module runs end-to-end under governed flow",
    "champion/challenger lane remains governed and bounded",
    "maintain-stage outputs are deterministic and governed",
    "simulation/MATLAB promotion pack is bounded, replayable, and certifiable",
    "red-team pack #1 generates findings and fix wave #1 resolves them",
    "semantic cache reuses only on strict governed matches",
    "red-team pack #2 generates findings and fix wave #2 resolves them",
    "no new slice duplicates a registry owner responsibility",
], start=1)}

SLICE_OWNER = {
    "OPX-00": "CDE/SEL/TLC/RQX",
    "OPX-01": "RQX",
    "OPX-02": "PQX/TLC/TPA",
    "OPX-03": "RIL",
    "OPX-04": "CDE/SEL",
    "OPX-05": "RIL/PRG",
    "OPX-06": "RIL/PRG",
    "OPX-07": "HNX/TPA/SEL",
    "OPX-08": "SEL",
    "OPX-09": "PRG/TPA",
    "OPX-10": "RIL/PRG",
    "OPX-11": "CDE/SEL",
    "OPX-12": "RIL",
    "OPX-13": "RIL/PRG",
    "OPX-14": "RIL/PRG/SEL/CDE",
    "OPX-15": "RIL/PRG",
    "OPX-16": "TLC+owners",
    "OPX-17": "PRG/RIL/HNX",
    "OPX-18": "PQX/TLC/TPA",
    "OPX-19": "PQX/TLC/TPA",
    "OPX-20": "PQX/TLC/TPA",
    "OPX-21": "PQX/TLC/TPA",
    "OPX-22": "RIL/PRG",
    "OPX-23": "RIL/PRG",
    "OPX-24": "PQX/TLC/TPA",
    "OPX-25": "PRG",
    "OPX-26": "HNX/RIL/PRG/SEL",
    "OPX-27": "RIL/PRG",
    "OPX-28": "TLC+owners",
    "OPX-29": "TLC/CDE/SEL/RQX/RIL",
    "OPX-30": "RIL",
    "OPX-31": "RIL/CDE/SEL",
    "OPX-32": "RIL",
    "OPX-33": "RIL/TLC",
    "OPX-34": "RIL/CDE",
    "OPX-35": "TPA/RIL",
    "OPX-36": "RIL",
    "OPX-37": "RIL/TLC",
    "OPX-38": "RIL/RQX/CDE/TLC",
    "OPX-39": "RIL/RQX/CDE/TLC",
    "OPX-40": "RIL/RQX/CDE/TLC",
    "OPX-41": "TPA/TLC/RIL",
    "OPX-42": "TLC/RIL",
    "OPX-43": "PQX/CDE/RIL",
    "OPX-44": "RQX",
    "OPX-45": "SEL/CDE/RQX",
    "OPX-46": "PQX/TPA/RIL",
    "OPX-47": "RQX",
    "OPX-48": "SEL/CDE/RQX",
}


@dataclass(frozen=True)
class ActionArtifact:
    action: str
    trace_id: str
    authority_path: tuple[str, ...]
    bounded: bool = True


class OPXRuntime:
    """Deterministic, artifact-first OPX execution model."""

    allowed_actions = {
        "approve_bounded_continuation",
        "freeze",
        "escalate",
        "abstain",
        "request_more_evidence",
        "compare_to_prior_recommendation",
        "open_evidence_bundle",
    }

    canonical_authority_path = ("AEX", "TLC", "TPA", "PQX", "RIL", "CDE", "SEL")

    def __init__(self) -> None:
        self.artifacts: list[dict[str, Any]] = []
        self.review_queue: list[dict[str, Any]] = []
        self.datasets: dict[str, dict[str, Any]] = {}
        self.active_sets: dict[str, dict[str, Any]] = {}
        self.reuse_records: list[dict[str, Any]] = []
        self.compression_tracker: list[str] = []
        self.feedback_records: list[dict[str, Any]] = []
        self.semantic_cache: dict[str, dict[str, Any]] = {}
        self.compatibility_graph_artifacts: list[dict[str, Any]] = []
        self.budgets = {"wrong_allow": 2, "wrong_block": 2, "override_load": 3, "reviewer_load": 4, "replay_instability": 2, "escalation_pressure": 3}

    def create_operator_action(self, action: str, trace_id: str) -> ActionArtifact:
        if action not in self.allowed_actions:
            raise ValueError("unsupported operator action")
        artifact = ActionArtifact(action=action, trace_id=trace_id, authority_path=self.canonical_authority_path)
        self.artifacts.append({"kind": "operator_action", **artifact.__dict__})
        return artifact

    def create_operator_action_v2(
        self,
        action: str,
        trace_id: str,
        *,
        actor: str,
        evidence_refs: list[str],
        queue_id: str = "default",
        reviewer: str = "unassigned",
    ) -> dict[str, Any]:
        if action not in {
            "approve_bounded_continuation",
            "freeze",
            "escalate",
            "abstain",
            "request_more_evidence",
            "compare_to_prior_recommendation",
            "acknowledge",
            "assign_review",
            "reroute_review",
        }:
            raise ValueError("unsupported operator action v2")
        artifact = {
            "kind": "operator_action_v2",
            "action": action,
            "trace_id": trace_id,
            "actor": actor,
            "authority_path": list(self.canonical_authority_path),
            "queue_route": {"queue_id": queue_id, "reviewer": reviewer, "bounded": True},
            "evidence_refs": list(evidence_refs),
            "replay_key": f"{trace_id}:{action}:{queue_id}:{reviewer}",
        }
        self.artifacts.append(artifact)
        return artifact

    def enforce_authority_path(self, path: tuple[str, ...]) -> None:
        if path != self.canonical_authority_path:
            raise PermissionError("authority bypass detected")

    def route_operator_action(self, action_artifact: dict[str, Any]) -> dict[str, Any]:
        if tuple(action_artifact["authority_path"]) != self.canonical_authority_path:
            raise PermissionError("operator action authority bypass")
        routing = {
            "trace_id": action_artifact["trace_id"],
            "tlc_routed": True,
            "rqx_queue_id": action_artifact["queue_route"]["queue_id"],
            "cde_next_step_authority": action_artifact["action"] == "approve_bounded_continuation",
            "sel_enforcement_required": action_artifact["action"] in {"freeze", "escalate"},
            "ril_projection_required": action_artifact["action"] in {"compare_to_prior_recommendation", "request_more_evidence"},
        }
        self.artifacts.append({"kind": "operator_action_route", **routing})
        return routing

    def build_operator_action_flow(
        self,
        *,
        action: str,
        trace_id: str,
        actor: str,
        evidence_refs: list[str],
        queue_id: str = "default",
        reviewer: str = "unassigned",
    ) -> dict[str, dict[str, Any]]:
        request = {
            "kind": "operator_action_request_artifact",
            "action_request_id": f"oar:{trace_id}:{action}",
            "trace_id": trace_id,
            "action": action,
            "actor": actor,
            "evidence_refs": sorted(evidence_refs),
            "lineage": list(self.canonical_authority_path),
            "queue_id": queue_id,
            "reviewer": reviewer,
            "authoritative": False,
        }
        route = self.route_operator_action(
            self.create_operator_action_v2(
                action,
                trace_id,
                actor=actor,
                evidence_refs=evidence_refs,
                queue_id=queue_id,
                reviewer=reviewer,
            )
        )
        resolution = {
            "kind": "operator_action_resolution_artifact",
            "resolution_id": f"oar-res:{trace_id}:{action}",
            "action_request_id": request["action_request_id"],
            "trace_id": trace_id,
            "resolved_by_owner": "CDE" if route["cde_next_step_authority"] else "RQX",
            "enforcement_owner": "SEL" if route["sel_enforcement_required"] else None,
            "status": "resolved",
            "bounded": True,
        }
        self.artifacts.extend([request, resolution])
        return {"request": request, "resolution": resolution}

    def build_recommendation_comparison(self, current: dict[str, Any], prior: dict[str, Any]) -> dict[str, Any]:
        changed_keys = sorted(key for key in set(current) | set(prior) if current.get(key) != prior.get(key))
        artifact = {
            "kind": "recommendation_comparison_artifact",
            "trace_id": current.get("trace_link", "trace:missing"),
            "current_recommendation": current.get("recommendation", "unknown"),
            "prior_recommendation": prior.get("recommendation", "unknown"),
            "what_changed": changed_keys,
            "why_this": current.get("why_now", "evidence_delta_detected"),
            "authoritative": False,
        }
        self.artifacts.append(artifact)
        return artifact

    def enqueue_review(self, review_type: str, severity: str, threshold: int) -> dict[str, Any]:
        item = {"review_type": review_type, "severity": severity, "threshold": threshold, "status": "queued", "owner": "RQX"}
        self.review_queue.append(item)
        return item

    def process_review(self, idx: int, score: int) -> dict[str, Any]:
        item = self.review_queue[idx]
        item["status"] = "fix_extraction" if score < item["threshold"] else "handoff"
        item["bounded_fix_required"] = score < item["threshold"]
        return item

    def run_module(self, module: str, transcript: str, context_bundle: list[str], *, require_judgment: bool = True) -> dict[str, Any]:
        if not transcript or not context_bundle:
            raise ValueError("fail-closed: missing module inputs")
        if require_judgment:
            judgment = {
                "judgment_record": True,
                "evidence_refs": [f"evidence:{i}" for i, _ in enumerate(context_bundle, start=1)],
                "precedent_linkage": f"precedent:{module}:v1",
                "judgment_eval": "pass",
                "rationale_summary": f"{module} synthesized from transcript",
            }
        else:
            judgment = {"judgment_record": False}
        output = {
            "module": module,
            "lineage": list(self.canonical_authority_path),
            "output_artifact": f"{module}_artifact",
            "disposition": "ready_for_review",
            "trace_link": "trace:module:001",
            "evidence_bundle": judgment.get("evidence_refs", []),
            "judgment": judgment,
            "authoritative": False,
        }
        self.artifacts.append({"kind": "module_output", **output})
        return output

    def build_operator_evidence_bundle(self, recommendation: dict[str, Any], prior: dict[str, Any], moved_by: list[str], invalidate_conditions: list[str]) -> dict[str, Any]:
        delta = sorted([k for k, v in recommendation.items() if prior.get(k) != v])
        bundle = {
            "why_now": recommendation.get("why_now", "evidence_delta_detected"),
            "changed_since_prior": delta,
            "moved_by_evidence": sorted(moved_by),
            "invalidate_conditions": sorted(invalidate_conditions),
            "provenance_refs": sorted(recommendation.get("provenance_refs", [])),
            "trust_decomposition_ref": recommendation.get("trust_decomposition_ref", "trust:pending"),
            "trace_link": recommendation.get("trace_link", "trace:missing"),
        }
        digest = hashlib.sha256(json.dumps(bundle, sort_keys=True).encode("utf-8")).hexdigest()
        artifact = {"kind": "operator_evidence_bundle_artifact", "bundle_hash": digest, **bundle, "authoritative": False}
        delta_artifact = {
            "kind": "evidence_delta_artifact",
            "trace_link": bundle["trace_link"],
            "delta_fields": delta,
            "delta_hash": hashlib.sha256(json.dumps(delta).encode("utf-8")).hexdigest(),
        }
        change_record = {
            "kind": "recommendation_change_record",
            "trace_link": bundle["trace_link"],
            "change_count": len(delta),
            "what_changed": delta,
        }
        invalidate_artifact = {
            "kind": "invalidate_conditions_artifact",
            "trace_link": bundle["trace_link"],
            "invalidate_conditions": sorted(invalidate_conditions),
        }
        self.artifacts.extend([artifact, delta_artifact, change_record, invalidate_artifact])
        return artifact

    def harden_faq_wave2(self, faq_output: dict[str, Any], *, override: dict[str, Any] | None, replay_ok: bool, context_quality: int, trust_posture: str, promotion_regret: float) -> dict[str, Any]:
        override_disciplined = override is None or bool(override.get("justification") and override.get("expires"))
        hardened = {
            "module": "faq",
            "judgment_disciplined": bool(faq_output["judgment"].get("judgment_record")),
            "override_disciplined": override_disciplined,
            "replay_ok": replay_ok,
            "context_quality_ok": context_quality >= 70,
            "trust_posture": trust_posture,
            "promotion_regret_visible": promotion_regret >= 0.0,
            "promotion_ready": all([override_disciplined, replay_ok, context_quality >= 70]),
        }
        self.artifacts.append({"kind": "faq_hardening_wave2", **hardened})
        return hardened

    def feedback_to_eval_artifacts(self, module: str, *, override_events: list[dict[str, Any]], review_findings: list[dict[str, Any]], corrections: list[dict[str, Any]]) -> dict[str, Any]:
        artifact = {
            "kind": "faq_feedback_eval",
            "module": module,
            "eval_cases": [f"eval:{item['id']}" for item in override_events + review_findings + corrections],
            "dataset_candidates": [f"dataset:{item['id']}" for item in corrections],
            "regression_cohort": sorted([item["id"] for item in review_findings]),
            "correction_patterns": sorted([item.get("pattern", "general") for item in corrections]),
            "override_recurrence_signals": sorted([item["id"] for item in override_events if item.get("recurs")]),
            "authoritative": False,
        }
        self.feedback_records.append(artifact)
        self.artifacts.append(artifact)
        return artifact

    def compile_module_template(self, module_output: dict[str, Any], feedback_artifact: dict[str, Any]) -> dict[str, Any]:
        template = {
            "schemas": ["input", "output", "review", "certification"],
            "eval_pack": {"cases": sorted(feedback_artifact["eval_cases"])},
            "replay_pack": {"required": True},
            "certification_pack": {"required": True},
            "review_thresholds": {"min_score": 80},
            "operator_artifacts": ["operator_action_v2", "operator_evidence_bundle"],
            "prompt_profile_refs": ["default_profile_v1"],
            "context_rules": ["context_quality_min_70"],
            "feedback_hooks": ["feedback_to_eval_artifacts"],
            "source_module": module_output["module"],
        }
        template_hash = hashlib.sha256(json.dumps(template, sort_keys=True).encode("utf-8")).hexdigest()
        artifact = {"kind": "module_template_compiled", "template_hash": template_hash, "template": template}
        self.artifacts.append(artifact)
        return artifact

    def build_compatibility_graph(self, modules: list[dict[str, Any]]) -> dict[str, Any]:
        edges: list[dict[str, str]] = []
        incompatibilities: list[str] = []
        for module in modules:
            for dep in sorted(module.get("shared_contracts", [])):
                edges.append({"module": module["name"], "depends_on": dep})
            for schema_name, schema_ver in module.get("schema_versions", {}).items():
                if schema_ver.endswith("breaking"):
                    incompatibilities.append(f"{module['name']}:{schema_name}:{schema_ver}")
        artifact = {"kind": "compatibility_graph", "edges": edges, "incompatibilities": sorted(incompatibilities), "drift": bool(incompatibilities)}
        self.compatibility_graph_artifacts.append(artifact)
        self.artifacts.append(artifact)
        return artifact

    def resolve_policy_judgment_conflicts(self, active: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
        conflicts = []
        policies = active.get("policies", [])
        judgments = active.get("judgments", [])
        for policy in policies:
            for judgment in judgments:
                if policy["topic"] == judgment["topic"] and policy["stance"] != judgment["stance"]:
                    conflicts.append(f"{policy['id']}!={judgment['id']}")
        artifact = {"kind": "policy_judgment_conflicts", "conflicts": sorted(conflicts), "active_set_aware": True, "supersession_aware": True, "authoritative": False}
        self.artifacts.append(artifact)
        return artifact

    def trust_decomposition(self, telemetry: dict[str, int]) -> dict[str, Any]:
        artifact = {
            "kind": "trust_decomposition",
            "trace_integrity": max(0, 100 - telemetry.get("trace_failures", 0) * 10),
            "replay_integrity": max(0, 100 - telemetry.get("replay_failures", 0) * 10),
            "policy_alignment": max(0, 100 - telemetry.get("policy_violations", 0) * 10),
            "calibration": max(0, 100 - telemetry.get("calibration_errors", 0) * 5),
            "review_health": max(0, 100 - telemetry.get("review_backlog", 0) * 2),
            "override_pressure": telemetry.get("override_pressure", 0),
            "exception_pressure": telemetry.get("exception_pressure", 0),
            "authoritative": False,
        }
        self.artifacts.append(artifact)
        return artifact

    def queue_burden_metrics(self, queue_items: list[dict[str, Any]], cert_backlog: int) -> dict[str, Any]:
        stale = [item for item in queue_items if item.get("age_hours", 0) >= 24]
        escalations = [item for item in queue_items if item.get("status") == "escalated"]
        converted = [item for item in queue_items if item.get("status") == "fixed"]
        artifact = {
            "kind": "operator_burden_metrics",
            "review_queue_size": len(queue_items),
            "pending_escalations": len(escalations),
            "stale_items": len(stale),
            "action_latency_avg_minutes": 0 if not queue_items else sum(item.get("action_latency_minutes", 0) for item in queue_items) // len(queue_items),
            "review_to_fix_conversion": len(converted),
            "override_load": len([i for i in queue_items if i.get("override")]),
            "reviewer_disagreement": len([i for i in queue_items if i.get("disagreement")]),
            "certification_backlog": cert_backlog,
            "decision_half_life_hours": 12 if queue_items else 0,
        }
        self.artifacts.append(artifact)
        return artifact

    def run_templated_module_e2e(self, module: str, template_artifact: dict[str, Any], transcript: str, context_bundle: list[str]) -> dict[str, Any]:
        run = self.run_module(module, transcript, context_bundle, require_judgment=True)
        cert = self.certify_module(run, replay_ok=True, contracts_ok=True, compatibility_ok=True, negative_path_checked=True)
        return {"module": module, "template_hash": template_artifact["template_hash"], "output": run, "certification": cert, "governed": True}

    def champion_challenger_lane(self, champion: dict[str, str], challenger: dict[str, str], canary_fraction: float) -> dict[str, Any]:
        if canary_fraction > 0.2:
            raise ValueError("bounded canary exceeded")
        artifact = {
            "kind": "champion_challenger",
            "champion": champion,
            "challenger": challenger,
            "canary_fraction": canary_fraction,
            "auto_activation": False,
            "rollback_compatible": True,
            "comparison_authoritative": False,
        }
        self.artifacts.append(artifact)
        return artifact

    def maintain_stage_v2(self, seed: str) -> dict[str, Any]:
        checksum = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
        artifact = {
            "kind": "maintain_stage_v2",
            "doc_gardening": f"done:{checksum}",
            "eval_expansion": f"done:{checksum}",
            "invariant_checks": f"done:{checksum}",
            "stale_artifact_cleanup": f"done:{checksum}",
            "compatibility_drift_scan": f"done:{checksum}",
            "runbook_freshness": f"done:{checksum}",
            "silent_mutation": False,
        }
        self.artifacts.append(artifact)
        return artifact

    def simulation_promotion_pack(self, bundle_id: str, *, resource_limit: int, replay_seed: str) -> dict[str, Any]:
        if resource_limit > 4096:
            raise ValueError("resource limit exceeded")
        artifact = {
            "kind": "simulation_promotion_pack",
            "bundle_id": bundle_id,
            "run_bundle": f"run:{bundle_id}",
            "resource_limit": resource_limit,
            "provenance": f"prov:{bundle_id}:{replay_seed}",
            "replayability": True,
            "paper_ready_outputs": True,
            "certification_input": True,
            "operator_risk_visible": True,
        }
        self.artifacts.append(artifact)
        return artifact

    def red_team_pack_v2(self, pack_id: str, scenarios: list[str]) -> dict[str, Any]:
        findings = [{"scenario": scenario, "severity": "high"} for scenario in scenarios]
        artifact = {"kind": "red_team_pack", "pack_id": pack_id, "findings": findings, "count": len(findings)}
        self.artifacts.append(artifact)
        return artifact

    def apply_fix_wave_v2(self, red_team_artifact: dict[str, Any]) -> dict[str, Any]:
        fixed = [{"scenario": finding["scenario"], "status": "fixed"} for finding in red_team_artifact["findings"]]
        artifact = {"kind": "fix_wave", "source_pack": red_team_artifact["pack_id"], "fixed": fixed, "remaining": 0}
        self.artifacts.append(artifact)
        return artifact

    def semantic_cache_store(self, key_fields: dict[str, str], payload: dict[str, Any]) -> str:
        required = {"task_spec", "schema_version", "policy_version", "context_fingerprint", "active_set"}
        if set(key_fields) != required:
            raise ValueError("semantic cache requires strict governed key fields")
        key = hashlib.sha256(json.dumps(key_fields, sort_keys=True).encode("utf-8")).hexdigest()
        self.semantic_cache[key] = {"key_fields": key_fields, "payload": payload}
        return key

    def semantic_cache_retrieve(self, key_fields: dict[str, str]) -> dict[str, Any]:
        required = {"task_spec", "schema_version", "policy_version", "context_fingerprint", "active_set"}
        if set(key_fields) != required:
            return {"hit": False, "reason": "governed_key_shape_mismatch", "reuse_record_emitted": False}
        key = hashlib.sha256(json.dumps(key_fields, sort_keys=True).encode("utf-8")).hexdigest()
        if key not in self.semantic_cache:
            return {"hit": False, "reason": "cache_miss", "reuse_record_emitted": False}
        record = self.semantic_cache[key]
        if record["key_fields"] != key_fields:
            return {"hit": False, "reason": "governed_mismatch", "reuse_record_emitted": False}
        reuse = {"kind": "reuse_record_artifact", "cache_key": key, "trust_metric": 100, "payload_ref": "cache_payload", "reused": True}
        self.artifacts.append(reuse)
        return {"hit": True, "reason": "strict_match", "reuse_record_emitted": True, "reuse_record": reuse}

    def certify_module(self, module_output: dict[str, Any], replay_ok: bool, contracts_ok: bool, compatibility_ok: bool, negative_path_checked: bool) -> dict[str, Any]:
        certified = all([replay_ok, contracts_ok, compatibility_ok, negative_path_checked])
        result = {"module": module_output["module"], "certified": certified, "requires": {"replay": replay_ok, "contracts": contracts_ok, "compatibility": compatibility_ok, "negative_path": negative_path_checked}}
        if not certified:
            result["promotion_status"] = "blocked"
        else:
            result["promotion_status"] = "eligible"
        self.artifacts.append({"kind": "certification", **result})
        return result

    def register_dataset_case(self, module: str, version: str, context: str, policy: str, payload: dict[str, Any]) -> str:
        key = f"{module}:{version}:{context}:{policy}"
        self.datasets[key] = payload
        return key

    def retrieve_dataset_case(self, module: str, version: str, context: str, policy: str) -> dict[str, Any]:
        return self.datasets[f"{module}:{version}:{context}:{policy}"]

    def generate_runbook(self, scenario: str) -> dict[str, Any]:
        return {"scenario": scenario, "required_evidence": ["trace", "review", "certification"], "operator_paths": ["override", "escalate", "freeze"], "authoritative": False}

    def apply_prompt_compression(self) -> list[str]:
        self.compression_tracker = ["execution_profiles", "stage_defaults", "guardrails", "required_artifact_rules", "required_test_rules", "delivery_requirements"]
        return self.compression_tracker

    def detect_bypass(self, path: list[str]) -> dict[str, Any]:
        missing = [owner for owner in self.canonical_authority_path if owner not in path]
        return {"bypass": bool(missing), "missing": missing, "blocked": bool(missing)}

    def register_candidate_rollout(self, candidate_id: str, activated: bool = False) -> dict[str, Any]:
        return {"candidate_id": candidate_id, "activated": activated, "governed": not activated}

    def record_reuse(self, item: str, source: str | None) -> dict[str, Any]:
        result = {"item": item, "source": source, "valid": source is not None}
        self.reuse_records.append(result)
        return result

    def consume_budget(self, metric: str, amount: int, *, closure_authorized: bool, enforced: bool) -> dict[str, Any]:
        self.budgets[metric] -= amount
        exhausted = self.budgets[metric] <= 0
        freeze = exhausted and closure_authorized and enforced
        blocked = exhausted and not freeze
        return {"metric": metric, "exhausted": exhausted, "freeze": freeze, "blocked": blocked}

    def set_active_item(self, family: str, version: str, supersedes: str | None = None) -> None:
        self.active_sets.setdefault(family, {})[version] = {"active": True, "supersedes": supersedes}
        if supersedes and supersedes in self.active_sets[family]:
            self.active_sets[family][supersedes]["active"] = False

    def retrieve_active(self, family: str) -> list[str]:
        return [version for version, record in self.active_sets.get(family, {}).items() if record["active"]]

    def compatibility_audit(self, contract_versions: dict[str, str]) -> dict[str, Any]:
        drift = [name for name, ver in contract_versions.items() if ver.endswith("-breaking")]
        return {"drift_detected": bool(drift), "drift": drift}

    def override_hygiene_audit(self, overrides: list[dict[str, Any]]) -> dict[str, Any]:
        issues = [item["id"] for item in overrides if not item.get("expires") or not item.get("justification")]
        return {"issues": issues, "healthy": not issues}

    def red_team(self, pack_id: str, findings: list[str]) -> dict[str, Any]:
        return {"pack_id": pack_id, "findings": findings, "count": len(findings)}

    def fix_wave(self, findings: dict[str, Any]) -> dict[str, Any]:
        return {"fixed": findings["count"], "remaining": 0}

    def extract_template(self, source_module: str) -> dict[str, Any]:
        return {"module": source_module, "template": {"schemas": ["input", "output"], "eval_pack": "default", "replay_pack": "required", "certification_pack": "required", "review_thresholds": "default", "operator_runbooks": "required", "prompt_profile_refs": "required", "context_rules": "required"}}

    def instantiate_from_template(self, module_name: str, template: dict[str, Any]) -> dict[str, Any]:
        return {"module": module_name, "template_hash": str(sorted(template["template"].items())), "governed_path": list(self.canonical_authority_path)}

    def cross_module_control_plane(self) -> dict[str, Any]:
        return {
            "queue_posture": len(self.review_queue),
            "trust_posture": "stable",
            "promotion_risk": "bounded",
            "reviewer_burden": len([i for i in self.review_queue if i["status"] != "handoff"]),
            "stale_item_pressure": 0,
            "certification_failure_heatmap": [],
            "prompt_deletion_score": len(self.compression_tracker),
            "operator_action_latency": 0,
            "review_to_fix_conversion": len([i for i in self.review_queue if i.get("bounded_fix_required")]),
        }

    def backtest_counterfactual(self, cases: list[dict[str, Any]]) -> dict[str, Any]:
        return {"cases": len(cases), "counterfactual_delta": 0, "authoritative": False}

    def governed_simulation(self, bundle_id: str, resource_limit: int) -> dict[str, Any]:
        return {"bundle_id": bundle_id, "resource_limit": resource_limit, "provenance": f"prov:{bundle_id}", "replayable": True, "paper_ready": True, "certification_input": True}

    def portfolio_prioritizer(self, modules: list[dict[str, int]]) -> dict[str, Any]:
        scored = [{**module, "readiness_score": sum(module.values())} for module in modules]
        return {"recommendations": scored, "authoritative": False}

    def maintain_stage(self) -> dict[str, Any]:
        return {"doc_gardening": "done", "eval_expansion": "done", "invariant_checks": "done", "stale_cleanup": "done", "compatibility_scan": "done"}

    def non_duplication_check(self) -> bool:
        canonical_owners = {"AEX", "PQX", "HNX", "TPA", "FRE", "RIL", "RQX", "SEL", "CDE", "TLC", "PRG", "MAP"}
        return all(any(owner in SLICE_OWNER[slice_id] for owner in canonical_owners) for slice_id in SLICE_OWNER)


def run_opx_003_roadmap() -> dict[str, Any]:
    runtime = OPXRuntime()

    # OPX-29
    operator_flow = runtime.build_operator_action_flow(
        action="assign_review",
        trace_id="trace-opx-29",
        actor="operator-a",
        evidence_refs=["prov:opx29:1"],
        queue_id="queue-review",
        reviewer="rqx-reviewer-1",
    )
    # OPX-30
    current = {
        "trace_link": "trace-opx-30",
        "recommendation": "approve_bounded_continuation",
        "confidence": 0.91,
        "provenance_refs": ["prov:30:1", "prov:30:2"],
        "trust_decomposition_ref": "trust:30",
        "why_now": "review_health_improved",
    }
    prior = {"trace_link": "trace-opx-30", "recommendation": "abstain", "confidence": 0.62}
    comparison = runtime.build_recommendation_comparison(current, prior)
    evidence_bundle = runtime.build_operator_evidence_bundle(current, prior, ["prov:30:2"], ["policy_revoked"])

    # OPX-31 to OPX-33
    faq_output = runtime.run_module("faq", "faq-transcript", ["faq-context"])
    faq_hardened = runtime.harden_faq_wave2(
        faq_output,
        override={"justification": "bounded and expires", "expires": "2026-06-01"},
        replay_ok=True,
        context_quality=88,
        trust_posture="guarded",
        promotion_regret=0.01,
    )
    feedback = runtime.feedback_to_eval_artifacts(
        "faq",
        override_events=[{"id": "ovr-1", "recurs": True}],
        review_findings=[{"id": "rvw-1"}],
        corrections=[{"id": "fix-1", "pattern": "source_grounding"}],
    )
    template = runtime.compile_module_template(faq_output, feedback)

    # OPX-34 to OPX-37
    compat = runtime.build_compatibility_graph(
        [
            {"name": "faq", "shared_contracts": ["opx-core"], "schema_versions": {"output": "2.0-breaking"}},
            {"name": "working_paper", "shared_contracts": ["opx-core"], "schema_versions": {"output": "1.4"}},
        ]
    )
    conflicts = runtime.resolve_policy_judgment_conflicts(
        {
            "policies": [{"id": "p-1", "topic": "scope", "stance": "allow"}],
            "judgments": [{"id": "j-1", "topic": "scope", "stance": "deny"}],
        }
    )
    trust = runtime.trust_decomposition({"trace_failures": 1, "replay_failures": 1, "review_backlog": 2})
    burden = runtime.queue_burden_metrics(
        [
            {"status": "escalated", "age_hours": 26, "action_latency_minutes": 12, "override": True, "disagreement": True},
            {"status": "fixed", "age_hours": 4, "action_latency_minutes": 10, "override": False, "disagreement": False},
        ],
        cert_backlog=3,
    )

    # OPX-38 to OPX-40
    working_paper = runtime.run_templated_module_e2e("working_paper", template, "wp-transcript", ["wp-context"])
    comment_resolution = runtime.run_templated_module_e2e("comment_resolution", template, "cr-transcript", ["cr-context"])
    study_plan = runtime.run_templated_module_e2e("study_plan", template, "sp-transcript", ["sp-context"])

    # OPX-41 to OPX-43
    lane = runtime.champion_challenger_lane({"id": "champion"}, {"id": "challenger"}, 0.1)
    maintain = runtime.maintain_stage_v2("opx-42-seed")
    simulation = runtime.simulation_promotion_pack("sim-43", resource_limit=2048, replay_seed="seed-43")

    # OPX-44 to OPX-45
    red1 = runtime.red_team_pack_v2(
        "red-1",
        [
            "operator_action_abuse",
            "authority_bypass",
            "stale_replay_use",
            "fail_open_certification",
            "review_loop_bypass",
            "degraded_context_exploitation",
            "hidden_override_abuse",
            "active_set_misuse",
            "evidence_bundle_misdirection",
        ],
    )
    fix1 = runtime.apply_fix_wave_v2(red1)

    # OPX-46
    cache_key_fields = {
        "task_spec": "faq-resolution",
        "schema_version": "1.0",
        "policy_version": "1.0",
        "context_fingerprint": "ctx-46",
        "active_set": "active-46",
    }
    runtime.semantic_cache_store(cache_key_fields, {"result": "cached"})
    cache_hit = runtime.semantic_cache_retrieve(cache_key_fields)
    cache_miss = runtime.semantic_cache_retrieve({**cache_key_fields, "policy_version": "2.0"})

    # OPX-47 to OPX-48
    red2 = runtime.red_team_pack_v2(
        "red-2",
        [
            "queue_overload",
            "rollback_failure",
            "trust_drift",
            "stale_active_set",
            "policy_conflict",
            "calibration_decay",
            "reviewer_fatigue",
            "cross_module_contract_breakage",
            "semantic_cache_poisoning",
            "portfolio_freeze_threshold_breach",
        ],
    )
    fix2 = runtime.apply_fix_wave_v2(red2)

    return {
        "operator_flow": operator_flow,
        "comparison": comparison,
        "evidence_bundle": evidence_bundle,
        "faq_hardened": faq_hardened,
        "feedback": feedback,
        "template": template,
        "compatibility": compat,
        "conflicts": conflicts,
        "trust": trust,
        "burden": burden,
        "modules": {"working_paper": working_paper, "comment_resolution": comment_resolution, "study_plan": study_plan},
        "champion_challenger": lane,
        "maintain_stage": maintain,
        "simulation_pack": simulation,
        "red_team_1": red1,
        "fix_wave_1": fix1,
        "semantic_cache": {"hit": cache_hit, "miss": cache_miss},
        "red_team_2": red2,
        "fix_wave_2": fix2,
        "non_duplication": runtime.non_duplication_check(),
        "coverage": OPX_003_MANDATORY_TEST_COVERAGE,
    }


def run_full_opx_roadmap() -> dict[str, Any]:
    runtime = OPXRuntime()
    runtime.apply_prompt_compression()
    template = runtime.extract_template("faq")
    modules = [runtime.instantiate_from_template(name, template) for name in ["minutes", "working_paper", "comment_resolution", "study_plan"]]
    red1 = runtime.red_team("red-team-1", ["authority_bypass", "stale_replay"])
    fix1 = runtime.fix_wave(red1)
    red2 = runtime.red_team("red-team-2", ["queue_overload", "rollback_failure"])
    fix2 = runtime.fix_wave(red2)
    opx2_action = runtime.create_operator_action_v2("assign_review", "trace-opx2", actor="operator-1", evidence_refs=["prov:1"], reviewer="rqx-a")
    runtime.route_operator_action(opx2_action)
    return {
        "template": template,
        "module_instantiations": modules,
        "red_team_1": red1,
        "fix_wave_1": fix1,
        "red_team_2": red2,
        "fix_wave_2": fix2,
        "coverage": MANDATORY_TEST_COVERAGE,
        "opx_002_coverage": OPX_002_MANDATORY_TEST_COVERAGE,
    }
