# PFX-02 — Current Contract Preflight BLOCK Fix + Root-Cause Auto-Repair

## Source artifacts used for diagnosis
- `outputs/contract_preflight/contract_preflight_report.json`
- `outputs/contract_preflight/contract_preflight_report.md`
- `outputs/contract_preflight/contract_preflight_result_artifact.json`
- `outputs/contract_preflight/contract_preflight_diagnosis_bundle.md`

## Exact current BLOCK root cause
1. `schema_example_failures` on `contracts/examples/system_registry_artifact.json`:
   - reserved systems had invalid shape (`owns` empty)
   - interaction edges contained unsupported `reason` property
2. Required-surface mapping drift for newly added runtime files had no deterministic test mapping in preflight policy map.

## Root-cause class
- **Primary class:** `schema_example_manifest_drift`
- **Systemic companion class:** `missing_required_surface_mapping`

## Current specific fix
- Repaired `system_registry_artifact` reserved entries and edge shape to satisfy schema.
- Restored canonical `context_bundle`/`context_conflict_record` schema+example compatibility where the prior change caused downstream amplification.
- Added governed required-surface override map file and runtime loader so newly added runtime files can be deterministically mapped to tests.
- Added deterministic tests for new runtime files (`task_registry`, `ai_adapter`, `eval_slice_runner`) and mapped them for required-surface preflight evaluation.

## Generalized governed diagnosis + auto-repair path
Extended repo-native contract-preflight autofix runtime:
- Runtime: `spectrum_systems/modules/runtime/github_pr_autofix_contract_preflight.py`
- CLI transport: `scripts/run_github_pr_autofix_contract_preflight.py`

### Supported bounded categories
- `missing_required_surface_mapping`
- `stale_test_fixture_contract`
- `stale_targeted_test_expectation`
- `missing_preflight_wrapper_or_authority_linkage`
- `trust_spine_input_expectation_mismatch`
- `control_surface_gap_mapping_missing`
- `pr_event_preflight_normalization_bug`
- `authority_evidence_ref_resolution_mismatch`
- `schema_example_manifest_drift`

### Fail-closed conditions
- missing input artifacts
- non-BLOCK preflight state
- unknown category
- unsafe write context (fork/untrusted)
- unsupported auto-repair category
- proposed mutated scope too broad
- validation replay failure
- preflight rerun still BLOCK/failed

### Validation + rerun requirements
- targeted validation is mandatory before success
- preflight rerun is mandatory before success
- result artifact remains failed if rerun does not ALLOW

### Workflow safety
- same-repo PR-only mutation path remains enforced by workflow guard
- fork PRs remain explicit skip/no-mutation

## Remaining risks / follow-on
- Add optional future category-specific validators for more granular producer/consumer fault clustering.
- Add additional repair-category fixtures to raise confidence for rare edge categories.
