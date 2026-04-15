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
]


def test_wpg_examples_validate() -> None:
    for name in WPG_CONTRACTS:
        validate_artifact(load_example(name), name)
