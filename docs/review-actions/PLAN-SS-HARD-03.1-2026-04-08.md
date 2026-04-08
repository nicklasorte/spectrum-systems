# Plan — SS-HARD-03.1 — 2026-04-08

## Prompt type
PLAN

## Roadmap item
SS-HARD-03.1 (Legacy Enforcement Isolation)

## Objective
Eliminate runtime reachability to `enforcement_engine.enforce_budget_decision` so governed runtime execution uses only canonical `enforce_control_decision`.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| spectrum_systems/modules/runtime/control_executor.py | MODIFY | Remove runtime bridge to legacy enforcement seam and route runtime execution to canonical enforcement artifacts. |
| spectrum_systems/modules/runtime/enforcement_engine.py | MODIFY | Remove runtime caller from legacy allowlist and keep legacy seam isolated to tests/fixtures only. |
| scripts/run_enforced_execution.py | MODIFY | Keep CLI aligned to canonical runtime enforcement output semantics after bridge removal. |
| tests/test_enforcement_engine.py | MODIFY | Update/strengthen static caller isolation checks for runtime legacy seam reachability. |
| tests/test_control_executor.py | MODIFY | Add focused coverage proving `execute_with_enforcement` uses canonical enforcement path. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_enforcement_engine.py`
2. `pytest tests/test_control_executor.py`
3. `pytest tests/test_replay_engine.py -k replay_run`

## Scope exclusions
- Do not redesign control orchestration or replay model.
- Do not touch bundle compiler / HRX surfaces.
- Do not introduce dual-path enforcement compatibility in runtime flows.
- Do not modify unrelated governance documents beyond this plan artifact.

## Dependencies
- SS-HARD-01, SS-HARD-02, and SS-HARD-03 hardening guarantees remain intact.
