# Plan — BATCH-Y3 — 2026-04-03

## Prompt type
PLAN

## Roadmap item
BATCH-Y3 — Trace & Replay Discoverability

## Objective
Add deterministic, operator-facing trace navigation, root-cause chain, replay entry points, and cross-artifact linking so operators can quickly trace, understand, and replay decisions across PRG→RVW→CTX→TPA→RDX→control/certification.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-Y3-2026-04-03.md | CREATE | Required PLAN-first artifact for multi-file contract/runtime changes |
| spectrum_systems/modules/runtime/system_cycle_operator.py | MODIFY | Emit trace_navigation, replay entry points, quick links, and root_cause_chain wiring |
| spectrum_systems/modules/runtime/system_integration_validator.py | MODIFY | Emit deterministic trace_navigation artifact map and replay entry points from cross-layer inputs |
| contracts/schemas/core_system_integration_validation.schema.json | MODIFY | Add trace_navigation contract fields and schema version bump |
| contracts/schemas/build_summary.schema.json | MODIFY | Add root_cause_chain, replay hooks, linking fields, and quick links with schema version bump |
| contracts/schemas/next_step_recommendation.schema.json | MODIFY | Add replay entry points, artifact linking fields, and quick links with schema version bump |
| contracts/examples/core_system_integration_validation.json | MODIFY | Keep example aligned with updated integration schema |
| contracts/examples/build_summary.json | MODIFY | Keep example aligned with updated build summary schema |
| contracts/examples/next_step_recommendation.json | MODIFY | Keep example aligned with updated recommendation schema |
| contracts/standards-manifest.json | MODIFY | Update schema versions for touched contracts |
| tests/test_system_integration_validator.py | MODIFY | Add trace_navigation determinism and replay entrypoint validity checks |
| tests/test_system_cycle_operator.py | MODIFY | Add root_cause_chain, replay hooks, quick links, and artifact linking completeness checks |

## Contracts touched
- `contracts/schemas/core_system_integration_validation.schema.json` (version bump)
- `contracts/schemas/build_summary.schema.json` (version bump)
- `contracts/schemas/next_step_recommendation.schema.json` (version bump)
- `contracts/standards-manifest.json` (version pin updates for touched contracts)

## Tests that must pass after execution
1. `pytest tests/test_system_cycle_operator.py`
2. `pytest tests/test_system_integration_validator.py`
3. `pytest tests/test_contracts.py`
4. `pytest tests/test_contract_enforcement.py`
5. `python scripts/run_contract_enforcement.py`
6. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not change roadmap execution core logic or authorization authority paths.
- Do not add any new module directories or repositories.
- Do not refactor unrelated runtime or contract artifacts outside declared files.

## Dependencies
- Existing BATCH-Y/BATCH-Y2 operator artifacts and integration contracts must remain authoritative and backward-compatible through deterministic contract evolution.
