# Plan — SRE-03 Replay Enforcement Test Migration — 2026-03-26

## Prompt type
PLAN

## Roadmap item
SRE-03

## Objective
Remove remaining legacy direct-`eval_summary` assumptions from replay/control-loop test surfaces and make replay-boundary rejection explicit while keeping replay-only enforcement intact.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-SRE-03-REPLAY-ENFORCEMENT-TEST-MIGRATION-2026-03-26.md | CREATE | Record PLAN for the follow-up migration slice. |
| PLANS.md | MODIFY | Register this active follow-up SRE-03 plan. |
| tests/helpers/replay_result_builder.py | MODIFY | Provide canonical replay fixture shape with required embedded governed artifacts. |
| spectrum_systems/modules/runtime/control_loop.py | MODIFY | Keep downstream runtime boundary replay-only and explicit fail-closed errors. |
| spectrum_systems/modules/runtime/control_loop_chaos.py | MODIFY | Ensure chaos execution path is replay-result based and boundary-aware. |
| tests/fixtures/control_loop_chaos_scenarios.json | MODIFY | Replace legacy `eval_summary` scenarios with canonical replay_result scenarios. |
| tests/test_control_loop_chaos.py | MODIFY | Migrate scenario tests to replay_result fixtures and explicit boundary rejection assertions. |
| tests/test_replay_engine.py | MODIFY | Remove legacy direct-eval_summary control-loop assumptions and align helpers with replay-only boundary. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_replay_engine.py -q`
2. `pytest tests/test_control_loop_chaos.py -q`
3. `pytest tests/test_evaluation_control.py tests/test_control_loop.py tests/test_alert_triggers.py tests/test_evaluation_monitor.py -q`

## Scope exclusions
- Do not add new runtime subsystems.
- Do not relax replay-only enforcement.
- Do not re-open direct eval_summary admission for downstream control-loop boundaries.
