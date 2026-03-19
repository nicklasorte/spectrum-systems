"""
Runtime Module — spectrum_systems/modules/runtime/

Provides the runtime compatibility enforcement layer (Prompt BC), the
run-bundle contract hardening layer (Prompt BD), the run output
normalization and evaluation layer (Prompt BE), the cross-run
intelligence and anomaly detection layer (Prompt BF), and the working
paper evidence pack synthesis layer (Prompt BG) for validating
execution bundles and their outputs.

Every validation produces a deterministic decision artifact that is
persisted and auditable.

Sub-modules
-----------
runtime_compatibility
    Core validation functions for MATLAB runtime version, platform,
    required artifacts, entrypoint, and cache-policy compliance (BC).
run_bundle
    Bundle contract and manifest hardening validators (BD).
run_output_evaluation
    Run output normalization, completeness evaluation, and decision
    artifact emission (BE).
cross_run_intelligence
    Cross-run metric alignment, anomaly detection, scenario ranking,
    and intelligence decision artifact emission (BF).
working_paper_synthesis
    Evidence pack synthesis, section mapping, ranked finding derivation,
    caveat extraction, and follow-up question generation (BG).
"""

from spectrum_systems.modules.runtime.runtime_compatibility import (
    classify_runtime_failure,
    derive_runtime_decision,
    validate_matlab_runtime_version,
    validate_platform_compatibility,
    validate_required_artifacts,
    validate_runtime_environment,
)
from spectrum_systems.modules.runtime.run_bundle import (
    RunBundleManifest,
    classify_bundle_failure,
    derive_bundle_summary,
    load_run_bundle_manifest,
    normalize_run_bundle_manifest,
    validate_bundle_contract,
    validate_expected_outputs,
    validate_input_paths,
    validate_output_contract,
    validate_provenance_fields,
    validate_run_bundle_manifest,
)
from spectrum_systems.modules.runtime.run_output_evaluation import (
    build_normalized_run_result,
    build_run_output_evaluation_decision,
    build_threshold_assessments,
    classify_evaluation_failure,
    compute_completeness,
    compute_readiness,
    detect_outlier_flags,
    evaluate_run_outputs,
    extract_provenance,
    extract_results_summary,
    get_required_metrics_for_study_type,
    infer_study_type,
    load_json_file,
    normalize_summary_metrics,
    resolve_manifest_output_paths,
    validate_normalized_run_result,
    validate_run_output_evaluation_decision,
)
from spectrum_systems.modules.runtime.cross_run_intelligence import (
    build_cross_run_comparison,
    build_cross_run_intelligence_decision,
    build_metric_comparisons,
    build_scenario_rankings,
    classify_cross_run_failure,
    collect_compared_runs,
    compare_normalized_runs,
    compute_summary_statistics,
    detect_cross_run_anomalies,
    detect_mixed_units,
    extract_metric_index,
    infer_comparison_study_type,
    load_normalized_run_result,
    validate_cross_run_comparison,
    validate_cross_run_intelligence_decision,
    validate_normalized_run_result_input,
)
from spectrum_systems.modules.runtime.working_paper_synthesis import (
    assign_evidence_to_sections,
    build_evidence_items_from_be,
    build_evidence_items_from_bf,
    build_working_paper_evidence_pack,
    build_working_paper_synthesis_decision,
    classify_synthesis_failure,
    collect_source_artifacts,
    compute_synthesis_status,
    derive_caveats,
    derive_followup_questions,
    derive_ranked_findings,
    infer_synthesis_study_type,
    load_governed_artifact,
    map_evidence_sections,
    synthesize_working_paper_evidence,
    validate_be_input,
    validate_bf_input,
    validate_working_paper_evidence_pack,
    validate_working_paper_synthesis_decision,
)

__all__ = [
    # BC — Runtime Compatibility
    "validate_runtime_environment",
    "validate_matlab_runtime_version",
    "validate_platform_compatibility",
    "validate_required_artifacts",
    "derive_runtime_decision",
    "classify_runtime_failure",
    # BD — Run Bundle Contract
    "RunBundleManifest",
    "load_run_bundle_manifest",
    "normalize_run_bundle_manifest",
    "validate_run_bundle_manifest",
    "validate_bundle_contract",
    "validate_expected_outputs",
    "validate_input_paths",
    "validate_output_contract",
    "validate_provenance_fields",
    "derive_bundle_summary",
    "classify_bundle_failure",
    # BE — Run Output Evaluation
    "load_json_file",
    "resolve_manifest_output_paths",
    "extract_results_summary",
    "extract_provenance",
    "infer_study_type",
    "get_required_metrics_for_study_type",
    "normalize_summary_metrics",
    "compute_completeness",
    "build_threshold_assessments",
    "detect_outlier_flags",
    "compute_readiness",
    "build_normalized_run_result",
    "classify_evaluation_failure",
    "build_run_output_evaluation_decision",
    "validate_normalized_run_result",
    "validate_run_output_evaluation_decision",
    "evaluate_run_outputs",
    # BF — Cross-Run Intelligence
    "load_normalized_run_result",
    "validate_normalized_run_result_input",
    "infer_comparison_study_type",
    "collect_compared_runs",
    "extract_metric_index",
    "build_metric_comparisons",
    "compute_summary_statistics",
    "detect_mixed_units",
    "build_scenario_rankings",
    "detect_cross_run_anomalies",
    "build_cross_run_comparison",
    "classify_cross_run_failure",
    "build_cross_run_intelligence_decision",
    "validate_cross_run_comparison",
    "validate_cross_run_intelligence_decision",
    "compare_normalized_runs",
    # BG — Working Paper Evidence Pack Synthesis
    "load_governed_artifact",
    "validate_be_input",
    "validate_bf_input",
    "infer_synthesis_study_type",
    "collect_source_artifacts",
    "map_evidence_sections",
    "build_evidence_items_from_be",
    "build_evidence_items_from_bf",
    "assign_evidence_to_sections",
    "derive_ranked_findings",
    "derive_caveats",
    "derive_followup_questions",
    "compute_synthesis_status",
    "build_working_paper_evidence_pack",
    "classify_synthesis_failure",
    "build_working_paper_synthesis_decision",
    "validate_working_paper_evidence_pack",
    "validate_working_paper_synthesis_decision",
    "synthesize_working_paper_evidence",
]
