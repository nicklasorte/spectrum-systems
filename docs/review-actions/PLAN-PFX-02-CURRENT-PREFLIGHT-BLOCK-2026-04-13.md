# PLAN — PFX-02 Current Contract Preflight BLOCK (2026-04-13)

## Prompt type
BUILD

## Diagnosis source artifacts
- `outputs/contract_preflight/contract_preflight_report.json`
- `outputs/contract_preflight/contract_preflight_report.md`
- `outputs/contract_preflight/contract_preflight_result_artifact.json`
- `outputs/contract_preflight/contract_preflight_diagnosis_bundle.md`

## Exact current blocking reasons
1. `schema_example_failures` includes `contracts/examples/system_registry_artifact.json` failing schema minItems for `systems[*].owns` (reserved systems were emitted with empty `owns`).
2. `missing_required_surface` contains:
   - `spectrum_systems/modules/runtime/ai_adapter.py`
   - `spectrum_systems/modules/runtime/eval_slice_runner.py`
   - `spectrum_systems/modules/runtime/task_registry.py`
   indicating required contract-surface runtime changes with no deterministic evaluation target mapping.
3. Additional producer/consumer failures are downstream amplification from a contract drift seam (`context_bundle` shape overwrite), but current strategy BLOCK can be removed by repairing schema/example compatibility and required surface mapping.

## Root-cause category
- Primary: `schema_example_manifest_drift`
- Secondary systemic class: `missing_required_surface_mapping` (required-surface-to-test mapping drift for new runtime files)

## Files in scope
- `contracts/examples/system_registry_artifact.json` (fix invalid reserved-system shape)
- `contracts/schemas/context_bundle.schema.json` + `contracts/examples/context_bundle.json` (restore canonical compatibility contract to stop producer/consumer drift amplification)
- `scripts/run_contract_preflight.py` (externalize required-surface overrides + deterministic mapping load)
- `docs/governance/preflight_required_surface_test_overrides.json` (governed machine-readable mapping)
- `spectrum_systems/modules/runtime/github_pr_autofix_contract_preflight.py` (bounded diagnosis+autorepair categories + allowed scope + rerun enforcement)
- `scripts/run_github_pr_autofix_contract_preflight.py` (transport/wiring for automation)
- `tests/test_contract_preflight.py`, `tests/test_github_pr_autofix_contract_preflight.py`, `tests/test_build_preflight_pqx_wrapper.py` (+ targeted new tests)
- `docs/reviews/pfx_02_current_fix_and_root_cause_autorepair.md`

## Validation plan
1. Run targeted tests for modified seams.
2. Re-run exact preflight commands from failure context.
3. Confirm `strategy_gate_decision` is not BLOCK for this case.
4. Run new automation tests proving fail-closed and bounded autorepair behavior.

## Scope exclusions
- No weakening of preflight BLOCK semantics.
- No broad CI auto-fixer outside contract-preflight bounded categories.
- No unrelated module refactors.

## Specific vs systemic
- Specific failure is fixed via schema/example compatibility + required surface mapping.
- Systemic class is handled by governed diagnosis/autorepair path for mapping/config drift and wrapper/evidence classes.
