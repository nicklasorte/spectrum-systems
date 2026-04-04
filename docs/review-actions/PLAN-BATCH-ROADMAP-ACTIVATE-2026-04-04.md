# Plan — BATCH-ROADMAP-ACTIVATE — 2026-04-04

## Prompt type
PLAN

## Roadmap item
BATCH-ROADMAP-ACTIVATE

## Objective
Store a governed roadmap artifact in-repo, load and deterministically select the next batch, execute exactly one bounded governed cycle through existing runtime paths, and write deterministic progress outputs.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-ROADMAP-ACTIVATE-2026-04-04.md | CREATE | Required PLAN-first artifact for this multi-file scope |
| PLANS.md | MODIFY | Register active plan entry |
| contracts/schemas/system_roadmap.schema.json | CREATE | New governed roadmap contract |
| contracts/examples/system_roadmap.json | CREATE | Golden-path governed roadmap example |
| contracts/standards-manifest.json | MODIFY | Publish new contract pin and version bump |
| docs/roadmaps/system_roadmap.md | MODIFY | Human-readable roadmap source aligned to governed JSON source of truth |
| spectrum_systems/modules/runtime/roadmap_selector.py | MODIFY | Add governed roadmap loader and deterministic batch selector logic |
| scripts/run_next_roadmap_batch.py | CREATE | CLI to run one governed roadmap batch and emit outputs |
| tests/test_roadmap_selector.py | MODIFY | Add governed roadmap load/selection/fail-closed determinism coverage |
| tests/test_system_cycle_operator.py | MODIFY | Add one-cycle governed roadmap activation wiring coverage |
| tests/test_contracts.py | MODIFY | Validate new contract example |

## Contracts touched
- Create `system_roadmap` schema + example.
- Update `contracts/standards-manifest.json` with version bump and `system_roadmap` registration.

## Tests that must pass after execution
1. `pytest tests/test_roadmap_selector.py`
2. `pytest tests/test_roadmap_multi_batch_executor.py`
3. `pytest tests/test_system_cycle_operator.py`
4. `pytest tests/test_contracts.py`
5. `pytest tests/test_contract_enforcement.py`
6. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not redesign runtime orchestration architecture.
- Do not add autonomous loop expansion logic beyond one bounded cycle.
- Do not refactor unrelated roadmap/runtime modules.

## Dependencies
- Existing governed execution surfaces (`run_system_cycle`, `next_cycle_decision`, `next_cycle_input_bundle`, `cycle_runner_result` contract) must remain authoritative and reused.
