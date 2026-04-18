from __future__ import annotations

from typing import Any, Dict, List

from spectrum_systems.modules.runtime.bne_utils import BNEBlockError, ensure_contract


STAGE_REQUIREMENTS = {
    "transcript_ingestion": ["contradiction_detection", "grounding_check"],
    "faq_generation": ["uncertainty_detection", "missing_question_detection", "answer_support_check"],
    "clustering": ["missing_question_detection"],
    "section_writing": ["grounding_check", "answer_support_check"],
    "working_paper_assembly": ["contradiction_detection", "grounding_check", "uncertainty_detection"],
}


def build_eval_coverage_requirement_profile(*, trace_id: str) -> Dict[str, Any]:
    return ensure_contract(
        {
            "artifact_type": "eval_coverage_requirement_profile",
            "schema_version": "1.0.0",
            "trace_id": trace_id,
            "outputs": {
                "stage_requirements": [
                    {"stage": stage, "required_eval_classes": required}
                    for stage, required in STAGE_REQUIREMENTS.items()
                ]
            },
        },
        "eval_coverage_requirement_profile",
    )


def enforce_eval_coverage(*, trace_id: str, stage: str, available_eval_classes: List[str]) -> Dict[str, Any]:
    required = STAGE_REQUIREMENTS.get(stage)
    if required is None:
        raise BNEBlockError(f"missing required eval coverage mapping for stage={stage}")

    covered = sorted(set(available_eval_classes))
    missing = sorted(set(required) - set(covered))
    decision = "BLOCK" if missing else "ALLOW"

    return ensure_contract(
        {
            "artifact_type": "wpg_eval_coverage_artifact",
            "schema_version": "1.0.0",
            "trace_id": trace_id,
            "outputs": {
                "active_stage_family": stage,
                "covered_eval_classes": sorted(set(covered) & set(required)),
                "missing_eval_classes": missing,
                "blocking_gaps": missing,
                "confidence_only_weak_spots": [],
                "decision": decision,
            },
        },
        "wpg_eval_coverage_artifact",
    )


def compute_wpg_eval_coverage(*, trace_id: str, available_eval_classes: list[str], active_stage_family: str) -> Dict[str, Any]:
    return enforce_eval_coverage(trace_id=trace_id, stage=active_stage_family, available_eval_classes=available_eval_classes)
