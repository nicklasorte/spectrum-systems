from __future__ import annotations

from typing import Any, Dict, List

from spectrum_systems.modules.wpg.common import ensure_contract, stable_hash


def compare_cross_run(*, run_a: Dict[str, Any], run_b: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
    a_sig = run_a.get("replay", {}).get("signature", "")
    b_sig = run_b.get("replay", {}).get("signature", "")
    drift = a_sig != b_sig
    return ensure_contract(
        {
            "artifact_type": "wpg_cross_run_comparison_artifact",
            "schema_version": "1.0.0",
            "trace_id": trace_id,
            "outputs": {
                "run_a_signature": a_sig,
                "run_b_signature": b_sig,
                "drift_detected": drift,
                "diff_summary": ["artifact drift detected"] if drift else ["no drift"],
            },
            "evaluation_refs": {
                "control_decision": {
                    "stage": "cross_run_comparison",
                    "decision": "WARN" if drift else "ALLOW",
                    "reasons": ["run_drift"] if drift else ["stable"],
                    "enforcement": {"action": "annotate" if drift else "proceed"},
                }
            },
        },
        "wpg_cross_run_comparison_artifact",
    )


def build_study_policy_profile(*, study_id: str, required_rules: List[str], trace_id: str) -> Dict[str, Any]:
    return ensure_contract(
        {
            "artifact_type": "wpg_study_policy_profile",
            "schema_version": "1.0.0",
            "trace_id": trace_id,
            "study_id": study_id,
            "required_rules": sorted(set(required_rules)),
            "policy_hash": stable_hash([study_id, sorted(set(required_rules))]),
            "evaluation_refs": {
                "control_decision": {
                    "stage": "study_policy",
                    "decision": "ALLOW" if required_rules else "BLOCK",
                    "reasons": ["policy_rules_loaded"] if required_rules else ["missing_policy_rules"],
                    "enforcement": {"action": "proceed" if required_rules else "trigger_repair"},
                }
            },
        },
        "wpg_study_policy_profile",
    )


def evaluate_quality_slo(*, quality_score: float, error_budget_remaining: float, trace_id: str) -> Dict[str, Any]:
    freeze = quality_score < 0.7 or error_budget_remaining <= 0
    decision = "FREEZE" if freeze else "ALLOW"
    return ensure_contract(
        {
            "artifact_type": "wpg_quality_slo",
            "schema_version": "1.0.0",
            "trace_id": trace_id,
            "quality_score": quality_score,
            "error_budget_remaining": error_budget_remaining,
            "freeze_required": freeze,
            "evaluation_refs": {
                "control_decision": {
                    "stage": "wpg_quality_slo",
                    "decision": decision,
                    "reasons": ["quality_degradation"] if freeze else ["slo_healthy"],
                    "enforcement": {"action": "halt" if freeze else "proceed"},
                }
            },
        },
        "wpg_quality_slo",
    )
