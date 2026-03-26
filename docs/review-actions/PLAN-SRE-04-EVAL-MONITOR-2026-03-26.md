# Plan — SRE-04 Evaluation Monitor Contract Migration — 2026-03-26

## Prompt type
PLAN

## Roadmap item
SRE-04 | Regression Suite | Baseline + regression lock

## Objective
Migrate evaluation_monitor to exclusively consume governed regression_run_result artifacts introduced by SRE-04 and remove legacy run_result assumptions.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| spectrum_systems/modules/runtime/evaluation_monitor.py | MODIFY | Derive monitor semantics from governed regression fields (blocked/regression_status/results lineage), fail-closed checks, no legacy fallbacks. |
| tests/test_evaluation_monitor.py | MODIFY | Rewrite tests and helper fixtures to consume only governed regression_run_result shape. |
| tests/fixtures/evaluation_monitor/healthy_run_1.json | MODIFY | Upgrade fixture to schema-valid governed regression_run_result. |
| tests/fixtures/evaluation_monitor/healthy_run_2.json | MODIFY | Upgrade fixture to schema-valid governed regression_run_result. |
| tests/fixtures/evaluation_monitor/degrading_run_1.json | MODIFY | Upgrade fixture to schema-valid governed regression_run_result. |
| tests/fixtures/evaluation_monitor/degrading_run_2.json | MODIFY | Upgrade fixture to schema-valid governed regression_run_result. |
| tests/fixtures/evaluation_monitor/critical_burnrate_run.json | MODIFY | Upgrade fixture to schema-valid governed regression_run_result. |
| tests/fixtures/evaluation_monitor/invalid_regression_result.json | MODIFY | Keep deterministic invalid fixture focused on governed contract violations. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest -q tests/test_evaluation_monitor.py`
2. `pytest -q`

## Scope exclusions
- Do not change regression_run_result schema in this migration.
- Do not redesign replay_decision_analysis schema.
- Do not modify unrelated runtime modules.

## Dependencies
- SRE-04 governed regression_run_result contract remains authoritative.
