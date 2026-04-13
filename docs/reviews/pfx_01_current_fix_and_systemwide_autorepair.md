# PFX-01 — Current Preflight BLOCK Fix + System-wide Governed Auto-Repair

## Exact root cause (artifact-based)
From `outputs/contract_preflight/contract_preflight_report.json` and sibling artifacts, the BLOCK was caused by test failures, not by missing wrapper/context or schema-example failures:
1. `producer_failures`: `tests/test_done_certification.py` failing after strict TAX/BAX/CAX lineage gating was made unconditional in active runtime mode.
2. `producer_failures`: `tests/test_system_handoff_integrity.py` failing because canonical handoff path `TPA -> FRE -> RIL -> CDE` was replaced instead of extended.
3. `consumer_failures`: mirrored done-certification failure.

No `missing_required_surface`, `pqx_required_context_enforcement` block, or trust-spine cohesion block was present in this failure case.

## Current-fix files changed
- `spectrum_systems/modules/governance/done_certification.py`
  - narrowed strict authority-lineage enforcement to explicit strict mode (`require_authority_lineage=true`) or explicit lineage refs present.
- `spectrum_systems/modules/runtime/system_registry_enforcer.py`
  - restored legacy canonical handoff edges and added TAX/BAX/CAX edges as extension rather than replacement.
- `tests/test_done_certification.py`
  - added strict-mode coverage asserting fail-closed block when lineage is explicitly required but missing.

## Current-fix validation
- targeted tests now pass:
  - `tests/test_done_certification.py`
  - `tests/test_system_handoff_integrity.py`
  - `tests/test_contract_preflight.py`
- preflight rerun with the same command shape now returns:
  - `status=passed`
  - `strategy_gate_decision=ALLOW`

## System-wide governed auto-repair design
Added repo-native fail-closed path:
- runtime: `spectrum_systems/modules/runtime/github_pr_autofix_contract_preflight.py`
- script entrypoint: `scripts/run_github_pr_autofix_contract_preflight.py`

Flow:
1. read `contract_preflight_result_artifact.json`
2. require `strategy_gate_decision=BLOCK`
3. read `contract_preflight_report.json`
4. diagnose category from artifact fields only
5. build bounded repair plan artifact
6. apply only auto-allowed bounded category repairs
7. run validation replay (`pytest tests/test_contract_preflight.py`)
8. rerun contract preflight
9. emit diagnosis/plan/attempt/validation/result artifacts
10. fail closed on unknown reason, unsafe context, validation failure, or rerun BLOCK/FREEZE

## Bounded repair categories supported
- `missing_required_surface_mapping`
- `stale_test_fixture_contract`
- `stale_targeted_test_expectation`
- `missing_preflight_wrapper_or_authority_linkage`
- `trust_spine_input_expectation_mismatch`
- `control_surface_gap_mapping_missing`

Current automatic apply is intentionally restricted to:
- `missing_preflight_wrapper_or_authority_linkage` (wrapper regeneration only)

All other categories are diagnosed and planned but not auto-mutated unless explicitly extended.

## New governed artifacts/contracts
- `preflight_block_diagnosis_record`
- `preflight_repair_plan_record`
- `preflight_repair_attempt_record`
- `preflight_repair_validation_record`
- `preflight_repair_result_record`

Added strict schemas, examples, and standards-manifest registrations.

## Workflow transport
Added `.github/workflows/pr-autofix-contract-preflight.yml`:
- triggers on failed `strategy-compliance` workflow runs for same-repo PRs
- skips fork PR mutation
- rebuilds wrapper + reruns preflight
- invokes governed preflight auto-repair entrypoint
- uploads resulting artifacts

## Fail-closed conditions
Auto-repair blocks when:
- preflight artifacts are missing or malformed
- strategy gate is not BLOCK
- diagnosis category is unknown
- context is fork/unsafe for mutation
- validation replay fails
- preflight rerun remains BLOCK/FREEZE or exits non-zero

## Remaining risks
- Non-wrapper categories are currently diagnosis+plan only (no automatic mutation) to preserve bounded safety.
- Future extension should add explicitly approved mutation policies per category with dedicated tests.
