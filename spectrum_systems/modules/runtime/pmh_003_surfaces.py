"""PMH-003 owner-native runtime surfaces.

This module adds bounded owner-native controls required by PMH-003 while keeping TLC
composition-only in runtime wiring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PRM003Surface:
    run_id: str

    def prompt_residue_registry(self, residue_fragments: list[str]) -> dict[str, Any]:
        unique = sorted({item.strip() for item in residue_fragments if item.strip()})
        return {
            "artifact_type": "prm_prompt_residue_registry_record",
            "owner": "PRM",
            "run_id": self.run_id,
            "status": "pass",
            "residue_fragments": unique,
        }

    def elision_compile(self, residue_registry: dict[str, Any], profile_id: str) -> dict[str, Any]:
        fragments = residue_registry.get("residue_fragments", [])
        return {
            "artifact_type": "prm_prompt_elision_compilation_record",
            "owner": "PRM",
            "run_id": self.run_id,
            "status": "pass" if fragments else "fail",
            "profile_id": profile_id,
            "compiled_defaults": [f"default:{fragment}" for fragment in fragments],
        }

    def reject_hidden_manual_sequencing(self, prompt_text: str) -> dict[str, Any]:
        blocked_patterns = ["rerun until", "manually sequence", "manual review/fix loop"]
        hits = [pattern for pattern in blocked_patterns if pattern in prompt_text.lower()]
        return {
            "artifact_type": "prm_hidden_manual_sequencing_rejection_result",
            "owner": "PRM",
            "run_id": self.run_id,
            "status": "fail" if hits else "pass",
            "reason_codes": [f"manual_sequence_pattern:{hit}" for hit in hits],
        }

    def default_profile_resolver(self, task_risk: str, stage: str) -> dict[str, Any]:
        matrix = {
            ("low", "build"): "thin-minimal-v3",
            ("medium", "validate"): "thin-guarded-v3",
            ("high", "review"): "thin-strict-v3",
        }
        profile_id = matrix.get((task_risk, stage), "thin-strict-v3")
        return {
            "artifact_type": "prm_default_prompt_profile_resolution_record",
            "owner": "PRM",
            "run_id": self.run_id,
            "status": "pass",
            "profile_id": profile_id,
        }


@dataclass(frozen=True)
class CON003Surface:
    run_id: str

    def simulation_runtime_gap(self, proof_artifacts: set[str], runtime_artifacts: set[str]) -> dict[str, Any]:
        missing_runtime = sorted(proof_artifacts - runtime_artifacts)
        return {
            "artifact_type": "con_simulation_runtime_gap_detection_result",
            "owner": "CON",
            "run_id": self.run_id,
            "status": "fail" if missing_runtime else "pass",
            "missing_runtime_artifacts": missing_runtime,
        }

    def concentration_threshold(self, orchestration_units: int, owner_native_units: int, max_ratio: float = 0.35) -> dict[str, Any]:
        total = max(1, orchestration_units + owner_native_units)
        ratio = orchestration_units / total
        return {
            "artifact_type": "con_orchestration_concentration_threshold_result",
            "owner": "CON",
            "run_id": self.run_id,
            "status": "fail" if ratio > max_ratio else "pass",
            "orchestration_ratio": round(ratio, 4),
            "max_ratio": max_ratio,
        }

    def owner_native_adoption_audit(self, total_execution_steps: int, owner_native_steps: int) -> dict[str, Any]:
        adoption_ratio = owner_native_steps / max(1, total_execution_steps)
        return {
            "artifact_type": "con_owner_native_adoption_audit_report",
            "owner": "CON",
            "run_id": self.run_id,
            "status": "pass" if adoption_ratio >= 0.8 else "fail",
            "owner_native_ratio": round(adoption_ratio, 4),
        }


@dataclass(frozen=True)
class CTX003Surface:
    run_id: str

    def context_recipe_enforcement_v2(self, recipe: dict[str, Any], stage: str) -> dict[str, Any]:
        required = {"recipe_id", "required_sources", "strict_mode"}
        missing = sorted(required - set(recipe))
        supports_stage = stage in set(recipe.get("approved_stages", [stage]))
        reason_codes = [f"missing_recipe_field:{field}" for field in missing]
        if not supports_stage:
            reason_codes.append("stage_not_approved_for_recipe")
        return {
            "artifact_type": "ctx_context_recipe_enforcement_v2_result",
            "owner": "CTX",
            "run_id": self.run_id,
            "status": "fail" if missing or not supports_stage else "pass",
            "reason_codes": reason_codes,
        }

    def conflict_fallback_hardening(self, has_conflict: bool, fallback_available: bool) -> dict[str, Any]:
        blocked = has_conflict and not fallback_available
        return {
            "artifact_type": "ctx_context_conflict_fallback_hardening_result",
            "owner": "CTX",
            "run_id": self.run_id,
            "status": "fail" if blocked else "pass",
            "decision": "halt" if blocked else "continue",
        }

    def no_recipe_no_compile(self, recipe_approved: bool) -> dict[str, Any]:
        return {
            "artifact_type": "ctx_no_recipe_no_compile_gate_result",
            "owner": "CTX",
            "run_id": self.run_id,
            "status": "pass" if recipe_approved else "fail",
        }


@dataclass(frozen=True)
class TLX003Surface:
    run_id: str

    def minimal_viable_toolset_registry(self, tools: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "artifact_type": "tlx_minimal_viable_toolset_registry",
            "owner": "TLX",
            "run_id": self.run_id,
            "status": "pass",
            "tools": tools,
        }

    def truncation_offload_standard(self, output_chars: int, hard_limit: int, offload_ref: str) -> dict[str, Any]:
        offloaded = output_chars > hard_limit
        return {
            "artifact_type": "tlx_tool_output_truncation_offload_record",
            "owner": "TLX",
            "run_id": self.run_id,
            "status": "pass",
            "offloaded": offloaded,
            "offload_ref": offload_ref if offloaded else "",
        }

    def stage_scoped_permission_profile(self, stage: str, allowed_tools: list[str], requested_tool: str) -> dict[str, Any]:
        return {
            "artifact_type": "tlx_stage_scoped_permission_profile_result",
            "owner": "TLX",
            "run_id": self.run_id,
            "status": "pass" if requested_tool in set(allowed_tools) else "fail",
            "stage": stage,
            "requested_tool": requested_tool,
        }

    def tool_error_next_step_contract(self, tool_id: str, failure_code: str) -> dict[str, Any]:
        return {
            "artifact_type": "tlx_tool_error_next_step_contract",
            "owner": "TLX",
            "run_id": self.run_id,
            "status": "pass",
            "tool_id": tool_id,
            "failure_code": failure_code,
            "next_steps": ["retrieve_offload", "retry_with_profile", "route_to_ril_review"],
        }


@dataclass(frozen=True)
class EVL003Surface:
    run_id: str

    def proof_runtime_parity_gate(self, proof_score: float, runtime_score: float, min_runtime: float = 0.8) -> dict[str, Any]:
        weak_runtime = runtime_score < min_runtime
        mismatch = proof_score > runtime_score
        return {
            "artifact_type": "evl_proof_runtime_parity_gate_result",
            "owner": "EVL",
            "run_id": self.run_id,
            "status": "fail" if weak_runtime or mismatch else "pass",
            "proof_score": proof_score,
            "runtime_score": runtime_score,
        }

    def substrate_eval_registry(self, required_families: list[str], completed_families: list[str]) -> dict[str, Any]:
        missing = sorted(set(required_families) - set(completed_families))
        return {
            "artifact_type": "evl_tool_context_substrate_eval_registry_record",
            "owner": "EVL",
            "run_id": self.run_id,
            "status": "fail" if missing else "pass",
            "missing_eval_families": missing,
        }

    def contradiction_triggered_eval_expansion(self, contradiction_detected: bool, seed_eval_ids: list[str]) -> dict[str, Any]:
        expansions = [f"exp-{eval_id}" for eval_id in seed_eval_ids] if contradiction_detected else []
        return {
            "artifact_type": "evl_contradiction_triggered_eval_expansion_record",
            "owner": "EVL",
            "run_id": self.run_id,
            "status": "pass",
            "expanded_eval_ids": expansions,
        }

    def proof_only_artifact_block(self, proof_only_behaviors: list[str]) -> dict[str, Any]:
        return {
            "artifact_type": "evl_proof_only_artifact_block_result",
            "owner": "EVL",
            "run_id": self.run_id,
            "status": "fail" if proof_only_behaviors else "pass",
            "proof_only_behaviors": sorted(proof_only_behaviors),
        }


@dataclass(frozen=True)
class CDE003Surface:
    run_id: str

    def runtime_adoption_readiness(self, owner_native_ratio: float, parity_status: str) -> dict[str, Any]:
        ready = owner_native_ratio >= 0.8 and parity_status == "pass"
        return {
            "artifact_type": "cde_runtime_adoption_readiness_decision",
            "owner": "CDE",
            "run_id": self.run_id,
            "status": "pass" if ready else "fail",
            "decision": "promote" if ready else "hold",
        }

    def saturation_suspend_decision(self, backlog_pressure: int, retry_pressure: int, capacity_posture: str) -> dict[str, Any]:
        suspend = backlog_pressure > 7 or retry_pressure > 7 or capacity_posture == "over_capacity"
        return {
            "artifact_type": "cde_saturation_suspend_decision",
            "owner": "CDE",
            "run_id": self.run_id,
            "status": "fail" if suspend else "pass",
            "decision": "suspend" if suspend else "continue",
        }

    def proof_runtime_mismatch_halt(self, proof_status: str, runtime_parity_status: str) -> dict[str, Any]:
        halt = proof_status == "pass" and runtime_parity_status == "fail"
        return {
            "artifact_type": "cde_proof_runtime_mismatch_halt_decision",
            "owner": "CDE",
            "run_id": self.run_id,
            "status": "fail" if halt else "pass",
            "decision": "halt" if halt else "continue",
        }

    def emergency_safe_default_switch(self, control_confidence: float) -> dict[str, Any]:
        enabled = control_confidence < 0.75
        return {
            "artifact_type": "cde_emergency_safe_default_switch_record",
            "owner": "CDE",
            "run_id": self.run_id,
            "status": "triggered" if enabled else "idle",
            "safe_default_forced": enabled,
        }


@dataclass(frozen=True)
class Saturation003Surface:
    run_id: str

    def slo_posture(self, burn_rate: float, max_burn_rate: float) -> dict[str, Any]:
        return {
            "artifact_type": "slo_prompt_minimal_automation_budget_posture",
            "owner": "SLO",
            "run_id": self.run_id,
            "status": "fail" if burn_rate > max_burn_rate else "pass",
            "burn_rate": burn_rate,
            "max_burn_rate": max_burn_rate,
        }

    def cap_budget(self, review_load: int, fix_load: int, rerun_load: int, limit: int) -> dict[str, Any]:
        total = review_load + fix_load + rerun_load
        return {
            "artifact_type": "cap_automation_capacity_budget_record",
            "owner": "CAP",
            "run_id": self.run_id,
            "status": "fail" if total > limit else "pass",
            "total_load": total,
            "limit": limit,
        }

    def qos_hotspot(self, aging_items: int, retry_storm: int) -> dict[str, Any]:
        hotspot = aging_items > 5 or retry_storm > 5
        return {
            "artifact_type": "qos_review_fix_backlog_aging_hotspot_record",
            "owner": "QOS",
            "run_id": self.run_id,
            "status": "fail" if hotspot else "pass",
            "aging_items": aging_items,
            "retry_storm": retry_storm,
        }


@dataclass(frozen=True)
class Parity003Surface:
    run_id: str

    def obs_parity(self, proof_signals: int, runtime_signals: int) -> dict[str, Any]:
        return {
            "artifact_type": "obs_proof_runtime_observability_parity_pack",
            "owner": "OBS",
            "run_id": self.run_id,
            "status": "pass" if runtime_signals >= proof_signals else "fail",
        }

    def lin_parity(self, owner_native_links: int, total_links: int) -> dict[str, Any]:
        ratio = owner_native_links / max(1, total_links)
        return {
            "artifact_type": "lin_owner_native_lineage_adoption_report",
            "owner": "LIN",
            "run_id": self.run_id,
            "status": "pass" if ratio >= 0.85 else "fail",
        }

    def rep_parity(self, proof_hash: str, runtime_hash: str) -> dict[str, Any]:
        return {
            "artifact_type": "rep_proof_runtime_replay_parity_pack",
            "owner": "REP",
            "run_id": self.run_id,
            "status": "pass" if proof_hash == runtime_hash else "fail",
        }


@dataclass(frozen=True)
class Learning003Surface:
    run_id: str

    def ail_manual_workaround_miner_v2(self, workaround_signals: list[str]) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for signal in workaround_signals:
            counts[signal] = counts.get(signal, 0) + 1
        return {
            "artifact_type": "ail_manual_workaround_miner_v2_record",
            "owner": "AIL",
            "run_id": self.run_id,
            "status": "pass",
            "clusters": [{"workaround": key, "count": value} for key, value in sorted(counts.items())],
            "non_authoritative": True,
        }

    def ail_divergence_clusterer(self, mismatches: list[str]) -> dict[str, Any]:
        buckets: dict[str, int] = {}
        for mismatch in mismatches:
            prefix = mismatch.split(":", 1)[0]
            buckets[prefix] = buckets.get(prefix, 0) + 1
        return {
            "artifact_type": "ail_proof_runtime_divergence_cluster_record",
            "owner": "AIL",
            "run_id": self.run_id,
            "status": "pass",
            "clusters": [{"cluster": key, "count": value} for key, value in sorted(buckets.items())],
            "non_authoritative": True,
        }

    def mnt_maintenance_v2(self) -> dict[str, Any]:
        return {
            "artifact_type": "mnt_prompt_tool_context_maintenance_v2_record",
            "owner": "MNT",
            "run_id": self.run_id,
            "status": "pass",
            "non_authoritative": True,
            "actions": [
                "prompt_garbage_collection_v2",
                "tool_context_drift_sweep",
                "contradiction_to_eval_loop",
            ],
        }
