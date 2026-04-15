from __future__ import annotations

from spectrum_systems.contracts import load_example, validate_artifact


WPG_CONTRACTS = [
    "question_set_artifact",
    "faq_artifact",
    "faq_report_artifact",
    "faq_cluster_artifact",
    "faq_conflict_artifact",
    "faq_confidence_artifact",
    "working_section_artifact",
    "working_paper_artifact",
    "unknowns_artifact",
    "wpg_delta_artifact",
    "transcript_artifact",
    "wpg_redteam_findings",
    "wpg_grounding_eval_case",
    "wpg_contradiction_propagation_record",
    "wpg_uncertainty_control_record",
    "narrative_integrity_record",
    "meeting_artifact",
    "meeting_minutes_artifact",
    "action_item_artifact",
    "action_linkage_record",
    "comment_artifact",
    "comment_mapping_record",
    "revision_plan_artifact",
    "revision_application_record",
    "comment_disposition_record",
    "wpg_redteam_findings_phase_b",
    "phase_checkpoint_record",
    "phase_transition_policy_result",
    "phase_resume_record",
    "phase_handoff_record",
    "phase_registry",
    "phase_requirement_profile",
    "artifact_family_phase_map",
]


def test_wpg_examples_validate() -> None:
    for name in WPG_CONTRACTS:
        validate_artifact(load_example(name), name)
