from __future__ import annotations
from typing import Any, Dict
from spectrum_systems.modules.runtime.bne_utils import ensure_contract

REQUIRED_CLASSES = [
    "transcript_ingress","faq_generation","contradiction_propagation","uncertainty_handling","minutes_generation","actions","comment_mapping","revision_planning_application","critique_loop","judgment_records","policy_enforcement","readiness","promotion"
]

def compute_wpg_eval_coverage(*, trace_id: str, available_eval_classes: list[str], active_stage_family: str) -> Dict[str, Any]:
    covered = sorted(set(available_eval_classes) & set(REQUIRED_CLASSES))
    missing = sorted(set(REQUIRED_CLASSES) - set(covered))
    blocking = [m for m in missing if m in {"transcript_ingress","readiness","promotion","policy_enforcement"}]
    return ensure_contract({
        "artifact_type": "wpg_eval_coverage_artifact",
        "schema_version": "1.0.0",
        "trace_id": trace_id,
        "outputs": {
            "active_stage_family": active_stage_family,
            "covered_eval_classes": covered,
            "missing_eval_classes": missing,
            "blocking_gaps": blocking,
            "confidence_only_weak_spots": [m for m in missing if m not in blocking],
            "decision": "BLOCK" if blocking else "ALLOW",
        },
    }, "wpg_eval_coverage_artifact")
