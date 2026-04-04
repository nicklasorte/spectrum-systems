# Plan — BATCH-PRG-SCHEMA — 2026-04-04

## Prompt type
PLAN

## Roadmap item
BATCH-PRG-SCHEMA — Program Semantics Hardening

## Objective
Convert program-related stop and reporting semantics from implicit/free-text signals into deterministic schema-bound fields across runtime outputs and operator artifacts.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-PRG-SCHEMA-2026-04-04.md | CREATE | Required PLAN artifact before multi-file contract/runtime BUILD work. |
| spectrum_systems/modules/runtime/roadmap_stop_reasons.py | MODIFY | Extend canonical stop-reason taxonomy with explicit program semantics. |
| spectrum_systems/modules/runtime/roadmap_multi_batch_executor.py | MODIFY | Emit structured program stop semantics and execution-path fields without changing enforcement flow. |
| spectrum_systems/modules/runtime/system_cycle_operator.py | MODIFY | Surface structured program semantics in build_summary and next_step_recommendation outputs. |
| contracts/schemas/roadmap_multi_batch_run_result.schema.json | MODIFY | Add required structured program semantics fields and expanded stop-reason enum. |
| contracts/schemas/build_summary.schema.json | MODIFY | Add required structured program semantics and enforce enum-bound stop fields. |
| contracts/schemas/next_step_recommendation.schema.json | MODIFY | Add required structured program semantics and enforce enum-bound stop fields. |
| contracts/examples/roadmap_multi_batch_run_result.json | MODIFY | Keep golden-path example aligned with schema additions. |
| contracts/examples/build_summary.json | MODIFY | Keep golden-path example aligned with schema additions. |
| contracts/examples/next_step_recommendation.json | MODIFY | Keep golden-path example aligned with schema additions. |
| contracts/standards-manifest.json | MODIFY | Bump changed contract versions and manifest publication version. |
| tests/test_roadmap_multi_batch_executor.py | MODIFY | Validate mapping of program violations to structured stop reasons and execution path semantics. |
| tests/test_system_cycle_operator.py | MODIFY | Validate required program semantics fields in operator artifacts. |
| tests/test_contract_enforcement.py | MODIFY | Add schema-level checks for stop-reason enum and required program semantics fields. |

## Contracts touched
- `roadmap_multi_batch_run_result` (additive schema + version bump)
- `build_summary` (additive schema + version bump)
- `next_step_recommendation` (additive schema + version bump)
- `standards_manifest` publication metadata/version pins update

## Tests that must pass after execution
1. `pytest tests/test_roadmap_multi_batch_executor.py`
2. `pytest tests/test_system_cycle_operator.py`
3. `pytest tests/test_contract_enforcement.py`
4. `pytest tests/test_contracts.py`
5. `python scripts/run_contract_enforcement.py`
6. `.codex/skills/contract-boundary-audit/run.sh`
7. `PLAN_FILES="docs/review-actions/PLAN-BATCH-PRG-SCHEMA-2026-04-04.md spectrum_systems/modules/runtime/roadmap_stop_reasons.py spectrum_systems/modules/runtime/roadmap_multi_batch_executor.py spectrum_systems/modules/runtime/system_cycle_operator.py contracts/schemas/roadmap_multi_batch_run_result.schema.json contracts/schemas/build_summary.schema.json contracts/schemas/next_step_recommendation.schema.json contracts/examples/roadmap_multi_batch_run_result.json contracts/examples/build_summary.json contracts/examples/next_step_recommendation.json contracts/standards-manifest.json tests/test_roadmap_multi_batch_executor.py tests/test_system_cycle_operator.py tests/test_contract_enforcement.py" .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not change continuation decision policy logic.
- Do not change authorization or enforcement outcomes.
- Do not refactor unrelated contracts/modules/tests.
- Do not introduce new repositories or modules.

## Dependencies
- Existing BATCH-PRG enforcement and reconciliation slices remain authoritative inputs.
