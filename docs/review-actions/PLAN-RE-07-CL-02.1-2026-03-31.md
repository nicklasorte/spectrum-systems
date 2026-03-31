# Plan — RE-07 CL-02.1 Error Budget Contract Repair — 2026-03-31

## Prompt type
PLAN

## Roadmap item
RE-07 CL-02.1 — Error Budget Contract Repair

## Objective
Repair canonical replay/control SLO and error-budget surfaces so replay-path observability metrics are fully represented in SLO objectives and error_budget_status objectives while preserving CL-02 fail-closed no-dead-metrics invariants.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-RE-07-CL-02.1-2026-03-31.md | CREATE | Required plan-first artifact for repair slice |
| PLANS.md | MODIFY | Register active CL-02.1 repair plan |
| contracts/examples/service_level_objective.json | MODIFY | Canonical SLO objective alignment for replay/control metric set |
| contracts/examples/error_budget_status.json | MODIFY | Canonical error-budget objective alignment with observability metrics |
| contracts/examples/observability_metrics.json | MODIFY | Canonical observability fixture alignment for replay-path metric set |
| spectrum_systems/modules/runtime/replay_engine.py | MODIFY | Ensure canonical/default replay SLO and policy cover emitted replay metrics |
| tests/helpers/replay_result_builder.py | MODIFY | Align canonical replay builder budget/objective reconciliation with full metric set |
| tests/test_replay_engine.py | MODIFY | Align replay test SLO/policy fixtures to canonical metric set |
| tests/test_control_integration.py | MODIFY | Align canonical replay artifact helper with CL-02 no-dead-metrics objective coverage |
| tests/fixtures/control_loop_chaos_scenarios.json | MODIFY | Repair canonical chaos replay artifacts to remove non-emitted baseline metric surface |

## Contracts touched
- contracts/examples/service_level_objective.json
- contracts/examples/error_budget_status.json
- contracts/examples/observability_metrics.json

## Tests that must pass after execution
1. `pytest tests/test_observability_metrics.py`
2. `pytest tests/test_error_budget.py`
3. `pytest tests/test_evaluation_control.py`
4. `pytest tests/test_control_loop.py`
5. `pytest tests/test_control_integration.py`
6. `pytest tests/test_control_loop_chaos.py`
7. `pytest tests/test_replay_engine.py`

## Scope exclusions
- Do not weaken CL-02 no-dead-metrics enforcement.
- Do not redesign control-loop runtime architecture.
- Do not implement CL-03 features.
- Do not refactor unrelated modules/tests.

## Dependencies
- CL-02 baseline implementation is present on current branch.
