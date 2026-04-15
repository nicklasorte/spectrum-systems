from __future__ import annotations

from typing import Any, Dict, List

from spectrum_systems.modules.wpg.common import ensure_contract


def build_lifecycle_certification(*, trace_id: str, required_controls: List[Dict[str, Any]]) -> Dict[str, Any]:
    blocking = [row for row in required_controls if row.get("decision") in {"BLOCK", "FREEZE"}]
    verdict = "PASS" if not blocking else "FAIL"
    return ensure_contract(
        {
            "artifact_type": "wpg_lifecycle_certification_artifact",
            "schema_version": "1.0.0",
            "trace_id": trace_id,
            "verdict": verdict,
            "blocking_controls": blocking,
            "final_review_doc": "docs/reviews/WPG_SYSTEM_CERTIFICATION.md",
            "evaluation_refs": {
                "control_decision": {
                    "stage": "lifecycle_certification",
                    "decision": "ALLOW" if verdict == "PASS" else "BLOCK",
                    "reasons": ["certified"] if verdict == "PASS" else ["blocking_controls_present"],
                    "enforcement": {"action": "proceed" if verdict == "PASS" else "trigger_repair"},
                }
            },
        },
        "wpg_lifecycle_certification_artifact",
    )


def build_reusable_template(*, trace_id: str, required_sections: List[str]) -> Dict[str, Any]:
    return ensure_contract(
        {
            "artifact_type": "wpg_reusable_template",
            "schema_version": "1.0.0",
            "trace_id": trace_id,
            "template_sections": required_sections,
            "evaluation_refs": {
                "control_decision": {
                    "stage": "reusable_template",
                    "decision": "ALLOW" if required_sections else "BLOCK",
                    "reasons": ["template_ready"] if required_sections else ["template_missing_sections"],
                    "enforcement": {"action": "proceed" if required_sections else "trigger_repair"},
                }
            },
        },
        "wpg_reusable_template",
    )
