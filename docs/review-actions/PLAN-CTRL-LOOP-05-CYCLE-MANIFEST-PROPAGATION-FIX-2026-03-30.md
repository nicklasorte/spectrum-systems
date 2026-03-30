# Plan — CTRL-LOOP-05 cycle_manifest propagation fix — 2026-03-30

## Prompt type
PLAN

## Roadmap item
CTRL-LOOP-05

## Objective
Restore contract propagation consistency by updating all cycle_manifest producers used by observability paths to explicitly include required lifecycle/rollout path fields with deterministic defaults.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CTRL-LOOP-05-CYCLE-MANIFEST-PROPAGATION-FIX-2026-03-30.md | CREATE | Required plan artifact for multi-file surgical fix |
| PLANS.md | MODIFY | Register active plan |
| tests/test_cycle_observability.py | MODIFY | Ensure manifest builder emits required lifecycle/rollout fields |
| tests/fixtures/autonomous_cycle/cycle_status_blocked_manifest.json | MODIFY | Align fixture with canonical cycle_manifest contract |

## Contracts touched
None (contract stays strict as-is).

## Tests that must pass after execution
1. `pytest tests/test_cycle_observability.py`
2. `pytest tests/test_cycle_runner.py`
3. `pytest tests/test_contracts.py`
4. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not relax cycle_manifest schema required fields.
- Do not add cycle_observability reader-side backward compatibility hacks.
- Do not modify control/runtime behavior beyond producer consistency updates.

## Dependencies
- Prior CTRL-LOOP-05 lifecycle enforcement changes are already present.
