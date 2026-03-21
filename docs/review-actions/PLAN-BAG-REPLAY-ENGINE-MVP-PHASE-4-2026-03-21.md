# Plan — BAG Replay Engine MVP Phase 4 — 2026-03-21

## Prompt type
PLAN

## Roadmap item
BAG — Replay Engine (MVP Phase 4)

## Objective
Add deterministic run-bundle replay that re-executes the existing enforcement pipeline, emits a schema-valid replay execution record with trace lineage, and exposes it via control executor + CLI with fail-closed behavior.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BAG-REPLAY-ENGINE-MVP-PHASE-4-2026-03-21.md | CREATE | Required PLAN artifact before multi-file BUILD work |
| PLANS.md | MODIFY | Register the new active plan |
| contracts/schemas/replay_execution_record.schema.json | CREATE | New governed artifact schema for replay execution records |
| contracts/standards-manifest.json | MODIFY | Version bump + register replay_execution_record contract |
| spectrum_systems/modules/runtime/replay_engine.py | MODIFY | Add replay_run() and schema validation for replay execution record |
| spectrum_systems/modules/runtime/control_executor.py | MODIFY | Add execute_with_replay() extending existing enforcement path |
| scripts/run_replay_execution.py | CREATE | Thin CLI for enforcement + replay execution |
| tests/test_replay_engine.py | MODIFY | Add deterministic replay engine tests and CLI exit-code tests |

## Contracts touched
- Create `contracts/schemas/replay_execution_record.schema.json` (new contract).
- Update `contracts/standards-manifest.json` with additive contract entry + version bump.

## Tests that must pass after execution
1. `pytest tests/test_replay_engine.py -q`
2. `pytest tests/test_enforcement_engine.py -q`
3. `pytest tests/test_evaluation_control_loop.py -q`
4. `pytest -q`
5. `pytest tests/test_contracts.py tests/test_contract_enforcement.py -q`
6. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not create a parallel validation/enforcement pipeline.
- Do not modify unrelated runtime modules outside replay/control executor integration points.
- Do not alter existing enforcement semantics except wiring deterministic replay comparison.
- Do not introduce network or external service dependencies.

## Dependencies
- Prompt BAF — Enforcement Wiring (MVP Phase 3) must remain intact.
- Existing run-bundle validation, monitor, budget governor, and enforcement contracts must remain authoritative.
