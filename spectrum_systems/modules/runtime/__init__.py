"""
Runtime Module — spectrum_systems/modules/runtime/

Provides the runtime compatibility enforcement layer (Prompt BC) and the
run-bundle contract hardening layer (Prompt BD) for validating execution
bundles BEFORE job execution.

Every validation produces a deterministic decision artifact that is
persisted and auditable.

Sub-modules
-----------
runtime_compatibility
    Core validation functions for MATLAB runtime version, platform,
    required artifacts, entrypoint, and cache-policy compliance (BC).
run_bundle
    Bundle contract and manifest hardening validators (BD).
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
]
