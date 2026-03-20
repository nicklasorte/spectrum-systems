"""
Runtime Module — spectrum_systems/modules/runtime/

Provides the runtime compatibility enforcement layer (Prompt BC), the
run-bundle contract hardening layer (Prompt BD), the run output
normalization and evaluation layer (Prompt BE), the cross-run
intelligence and anomaly detection layer (Prompt BF), the working
paper evidence pack synthesis layer (Prompt BG), the SLO control
layer (Prompt BR) for validating execution bundles and their outputs,
and the artifact lineage system (Prompt BS) for full pipeline
traceability.

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
slo_control
    SLO evaluation, error budget computation, and proceed/block
    determination across BE, BF, and BG outputs (BR).
artifact_lineage
    Strict deterministic lineage system connecting all pipeline artifacts
    with full traceability and integrity enforcement (BS).
trace_store
    Durable file-backed trace persistence, retrieval, and validation (BN).
replay_engine
    Deterministic replay of prior execution traces for debugging, audit,
    and learning workflows (BP).
regression_harness
    Batch regression suite execution, drift detection, and CI-ready
    aggregate run result emission (BR).
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
from spectrum_systems.modules.runtime.slo_control import (
    build_slo_evaluation_artifact,
    classify_violation,
    compute_completeness_sli,
    compute_error_budget,
    compute_slo_status,
    compute_timeliness_sli,
    compute_traceability_integrity_sli,
    compute_traceability_sli,
    determine_allowed_to_proceed,
    load_inputs,
    run_slo_control,
    validate_inputs_against_schema,
    validate_output_against_schema,
)
from spectrum_systems.modules.runtime.artifact_lineage import (
    ARTIFACT_TYPES,
    build_full_lineage_graph,
    compute_lineage_depth,
    compute_root_artifacts,
    create_artifact_metadata,
    detect_lineage_gaps,
    enforce_no_orphans,
    link_artifacts,
    trace_to_leaves,
    trace_to_root,
    validate_against_schema as validate_lineage_against_schema,
    validate_full_registry,
    validate_lineage_chain,
)
from spectrum_systems.modules.runtime.trace_store import (
    delete_trace,
    list_traces,
    load_trace,
    persist_trace,
    validate_persisted_trace,
)
from spectrum_systems.modules.runtime.replay_engine import (
    build_replay_record,
    compare_replay_outputs,
    execute_replay,
    validate_replay_prerequisites,
    validate_replay_result,
)
from spectrum_systems.modules.runtime.regression_harness import (
    InvalidSuiteError,
    MissingTraceError,
    RegressionHarnessError,
    aggregate_regression_results,
    evaluate_trace_pass_fail,
    load_regression_suite,
    run_regression_suite,
    run_trace_regression,
    validate_regression_run_result,
    validate_regression_suite,
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
    # BR — SLO Control Layer
    "load_inputs",
    "validate_inputs_against_schema",
    "compute_completeness_sli",
    "compute_timeliness_sli",
    "compute_traceability_sli",
    "compute_traceability_integrity_sli",
    "classify_violation",
    "compute_slo_status",
    "compute_error_budget",
    "determine_allowed_to_proceed",
    "build_slo_evaluation_artifact",
    "validate_output_against_schema",
    "run_slo_control",
    # BS — Artifact Lineage System
    "ARTIFACT_TYPES",
    "create_artifact_metadata",
    "link_artifacts",
    "compute_lineage_depth",
    "compute_root_artifacts",
    "validate_lineage_chain",
    "build_full_lineage_graph",
    "trace_to_root",
    "trace_to_leaves",
    "detect_lineage_gaps",
    "enforce_no_orphans",
    "validate_lineage_against_schema",
    "validate_full_registry",
    # BN — Trace Persistence (trace_store)
    "persist_trace",
    "load_trace",
    "list_traces",
    "delete_trace",
    "validate_persisted_trace",
    # BP — Replay Engine
    "build_replay_record",
    "validate_replay_prerequisites",
    "execute_replay",
    "compare_replay_outputs",
    "validate_replay_result",
    # BR — Replay Regression Harness
    "InvalidSuiteError",
    "MissingTraceError",
    "RegressionHarnessError",
    "load_regression_suite",
    "validate_regression_suite",
    "run_trace_regression",
    "evaluate_trace_pass_fail",
    "aggregate_regression_results",
    "validate_regression_run_result",
    "run_regression_suite",
]
