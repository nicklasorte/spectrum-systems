from __future__ import annotations

from typing import Any, Dict, List

from spectrum_systems.modules.wpg.common import ensure_contract


def _policy_artifact(artifact_type: str, *, trace_id: str, policy_rules: List[str], decision: str = "ALLOW") -> Dict[str, Any]:
    return ensure_contract(
        {
            "artifact_type": artifact_type,
            "schema_version": "1.0.0",
            "trace_id": trace_id,
            "policy_rules": policy_rules,
            "evaluation_refs": {
                "control_decision": {
                    "stage": artifact_type,
                    "decision": decision,
                    "reasons": ["policy_loaded"] if policy_rules else ["policy_missing"],
                    "enforcement": {"action": "proceed" if decision == "ALLOW" else "trigger_repair"},
                }
            },
        },
        artifact_type,
    )


def build_governance_policy_pack(*, trace_id: str) -> Dict[str, Dict[str, Any]]:
    return {
        "eval_requirement_profile": _policy_artifact("eval_requirement_profile", trace_id=trace_id, policy_rules=["require_eval_suite", "require_reproducibility"]),
        "review_trigger_policy": _policy_artifact("review_trigger_policy", trace_id=trace_id, policy_rules=["trigger_on_block", "trigger_on_drift"]),
        "redteam_trigger_policy": _policy_artifact("redteam_trigger_policy", trace_id=trace_id, policy_rules=["trigger_on_high_risk"]),
        "promotion_requirements": _policy_artifact("promotion_requirements", trace_id=trace_id, policy_rules=["require_certification", "require_green_eval"]),
        "override_policy": _policy_artifact("override_policy", trace_id=trace_id, policy_rules=["require_justification", "require_audit_log"]),
        "reuse_policy": _policy_artifact("reuse_policy", trace_id=trace_id, policy_rules=["require_precedent_link", "require_scope_match"]),
        "context_admission_policy": _policy_artifact("context_admission_policy", trace_id=trace_id, policy_rules=["allow_governed_only", "deny_ungoverned"]),
        "policy_canary": _policy_artifact("policy_canary", trace_id=trace_id, policy_rules=["sample_policy_paths", "freeze_on_regression"]),
    }
