# Plan — BATCH-CYCLE-LOOP — 2026-04-04

## Prompt type
PLAN

## Roadmap item
BATCH-CYCLE-LOOP — Bounded Next-Cycle Automation

## Objective
Implement deterministic bounded cycle continuation decisioning and handoff artifacts so each governed run emits an explicit next-cycle decision and next-cycle input bundle, then stops.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-CYCLE-LOOP-2026-04-04.md | CREATE | Required plan-first artifact for this multi-file contract+runtime change. |
| PLANS.md | MODIFY | Register active plan in repository plan index. |
| contracts/schemas/next_cycle_decision.schema.json | CREATE | Add governed schema for deterministic cycle continuation decision artifact. |
| contracts/schemas/next_cycle_input_bundle.schema.json | CREATE | Add governed schema for deterministic next-cycle machine handoff bundle artifact. |
| contracts/examples/next_cycle_decision.json | CREATE | Provide golden-path example payload for next_cycle_decision contract. |
| contracts/examples/next_cycle_input_bundle.json | CREATE | Provide golden-path example payload for next_cycle_input_bundle contract. |
| contracts/examples/next_step_recommendation.json | MODIFY | Keep golden-path example aligned with schema additions for next-cycle decision surfaces. |
| contracts/examples/build_summary.json | MODIFY | Keep golden-path example aligned with schema additions for cycle decision and handoff references. |
| contracts/schemas/next_step_recommendation.schema.json | MODIFY | Extend operator artifact contract to expose next-cycle decision references and blockers/conditions clearly. |
| contracts/schemas/build_summary.schema.json | MODIFY | Extend cycle summary contract to surface cycle-decision and handoff bundle references/details. |
| spectrum_systems/modules/runtime/system_cycle_operator.py | MODIFY | Implement deterministic decide_next_cycle / input bundle construction and wire outputs to operator artifacts. |
| tests/test_system_cycle_operator.py | MODIFY | Add deterministic decision and bundle behavior tests plus operator-surface assertions. |
| tests/test_contracts.py | MODIFY | Validate new contract examples in contract test suite. |
| contracts/standards-manifest.json | MODIFY | Publish schema versions and register new artifact contracts in canonical standards manifest. |
| docs/runbooks/cycle_runner.md | MODIFY | Update process flow docs for bounded cycle → continuation decision → input bundle → stop sequence. |

## Contracts touched
- `next_cycle_decision` (new)
- `next_cycle_input_bundle` (new)
- `next_step_recommendation` (schema update)
- `build_summary` (schema update)
- `standards_manifest` (version and contract registry update)

## Tests that must pass after execution
1. `pytest tests/test_system_cycle_operator.py`
2. `pytest tests/test_roadmap_multi_batch_executor.py`
3. `pytest tests/test_program_layer.py`
4. `pytest tests/test_system_mvp_validation.py`
5. `pytest tests/test_contracts.py`
6. `pytest tests/test_contract_enforcement.py`
7. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not introduce autonomous recursive scheduling or background loop workers.
- Do not redesign PQX/TPA architecture; only wire deterministic decision outputs to existing governed flow.
- Do not refactor unrelated runtime modules or tests outside declared files.

## Dependencies
- Existing BATCH-RDX / BATCH-RDX-LOOP / BATCH-MVP foundations must remain authoritative for bounded execution.
