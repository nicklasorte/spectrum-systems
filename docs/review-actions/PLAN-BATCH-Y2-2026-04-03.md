# Plan — BATCH-Y2 — 2026-04-03

## Prompt type
PLAN

## Roadmap item
BATCH-Y2

## Objective
Upgrade deterministic next-step recommendation generation to evaluate multiple candidates, rank them with explicit deterministic logic, choose the best next step, and explain why alternatives were not selected.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-Y2-2026-04-03.md | CREATE | Required plan-first artifact for BATCH-Y2 implementation. |
| spectrum_systems/modules/runtime/system_cycle_operator.py | MODIFY | Implement candidate generation, deterministic ranking, and selected/rejected next-step reasoning. |
| contracts/schemas/next_step_recommendation.schema.json | MODIFY | Extend contract for candidate list, ranking metadata, and why-not-selected structure. |
| contracts/examples/next_step_recommendation.json | MODIFY | Keep golden-path example aligned with updated next_step_recommendation contract. |
| contracts/standards-manifest.json | MODIFY | Version bump metadata for updated next_step_recommendation schema contract. |
| tests/test_system_cycle_operator.py | MODIFY | Add deterministic tests for candidate generation, ranking, selection, and blocked handling. |
| tests/test_operator_shakeout.py | MODIFY | Ensure shakeout expectations remain valid with richer recommendation structure. |

## Contracts touched
- `contracts/schemas/next_step_recommendation.schema.json` (version bump required)
- `contracts/standards-manifest.json`

## Tests that must pass after execution
1. `pytest tests/test_system_cycle_operator.py`
2. `pytest tests/test_operator_shakeout.py`
3. `pytest tests/test_contracts.py`
4. `pytest tests/test_contract_enforcement.py`
5. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not change roadmap eligibility logic in unrelated orchestration modules.
- Do not alter control authorization/freeze semantics.
- Do not modify unrelated artifact contracts.

## Dependencies
- BATCH-Y1 artifacts must remain available and unchanged in semantics where not explicitly extended.
