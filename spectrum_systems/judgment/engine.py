from __future__ import annotations

from typing import Any, Dict


class JudgmentPolicyError(RuntimeError):
    """Raised when deterministic judgment policy cannot be applied."""


def apply_judgment_policy(policy: Dict[str, Any], record: Dict[str, Any]) -> Dict[str, Any]:
    threshold = float(policy.get("min_confidence", 0.0))
    confidence = float(record.get("confidence", 0.0))
    if confidence < threshold:
        outcome = "needs_review"
    else:
        outcome = "accepted"
    return {
        "artifact_type": "judgment_application_record",
        "schema_version": "1.0.0",
        "application_id": f"jar-{abs(hash((policy.get('policy_id','policy'), record.get('judgment_id','judgment')))) & ((1<<64)-1):016x}",
        "judgment_id": record.get("judgment_id", "judgment"),
        "policy_id": policy.get("policy_id", "policy"),
        "applied_outcome": outcome,
        "conditions_under_which_decision_changes": policy.get(
            "conditions_under_which_decision_changes",
            ["confidence_below_threshold", "new_contradictory_evidence"],
        ),
    }
