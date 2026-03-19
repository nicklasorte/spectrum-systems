"""
Runtime Module — spectrum_systems/modules/runtime/

Provides the runtime compatibility enforcement layer (Prompt BC), the
run-bundle contract hardening layer (Prompt BD), and the run output
normalization and evaluation layer (Prompt BE) for validating execution
bundles and their outputs.

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
]
