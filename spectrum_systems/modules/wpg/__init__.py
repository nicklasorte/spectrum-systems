from spectrum_systems.modules.wpg.common import StageContext, WPGError
from spectrum_systems.modules.wpg.faq_clusterer import cluster_faqs
from spectrum_systems.modules.wpg.faq_formatter import format_faq_for_report
from spectrum_systems.modules.wpg.faq_generator import build_faq
from spectrum_systems.modules.wpg.question_extractor import extract_questions
from spectrum_systems.modules.wpg.section_writer import write_sections
from spectrum_systems.modules.wpg.phase_governance import (
    build_phase_checkpoint_record,
    build_phase_handoff_record,
    build_phase_resume_record,
    default_phase_registry,
    evaluate_phase_transition,
)
from spectrum_systems.modules.wpg.working_paper_assembler import assemble_working_paper
from spectrum_systems.modules.wpg.critique_memory import (
    ingest_comment_matrix_signal,
    build_agency_critique_profile,
    build_industry_critique_profile,
    retrieve_critique_memory,
)
from spectrum_systems.modules.wpg.critique_loop import run_multi_pass_critique
from spectrum_systems.modules.wpg.judgment import build_judgment_record, retrieve_precedent, evaluate_judgment
from spectrum_systems.modules.wpg.policy_ops import compare_cross_run, build_study_policy_profile, evaluate_quality_slo
from spectrum_systems.modules.wpg.governance_offload import build_governance_policy_pack
from spectrum_systems.modules.wpg.certification import build_lifecycle_certification, build_reusable_template

__all__ = [
    "StageContext",
    "WPGError",
    "extract_questions",
    "build_faq",
    "format_faq_for_report",
    "cluster_faqs",
    "write_sections",
    "assemble_working_paper",
    "default_phase_registry",
    "build_phase_checkpoint_record",
    "evaluate_phase_transition",
    "build_phase_resume_record",
    "build_phase_handoff_record",
    "ingest_comment_matrix_signal",
    "build_agency_critique_profile",
    "build_industry_critique_profile",
    "retrieve_critique_memory",
    "run_multi_pass_critique",
    "build_judgment_record",
    "retrieve_precedent",
    "evaluate_judgment",
    "compare_cross_run",
    "build_study_policy_profile",
    "evaluate_quality_slo",
    "build_governance_policy_pack",
    "build_lifecycle_certification",
    "build_reusable_template",
]
