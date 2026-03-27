# Plan — SRE-09/SRE-10 Test Scaffolding Tightening — 2026-03-27

## Prompt type
PLAN

## Roadmap item
SRE-09/SRE-10 follow-on — test/fixture alignment with replay budget consistency hardening

## Objective
Align chaos/eval-ci test scaffolding and replay fixture builders with strict runtime replay budget-consistency enforcement without weakening control-loop governance.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-SRE-09-SRE-10-TEST-SCAFFOLD-TIGHTENING-2026-03-27.md | CREATE | Required PLAN for multi-file test/fixture changes |
| PLANS.md | MODIFY | Register active follow-on plan |
| tests/helpers/replay_result_builder.py | MODIFY | Add deterministic helper to keep observability metrics and error-budget objectives consistent |
| tests/test_control_loop_chaos.py | MODIFY | Update malformed-input assertions and use consistent replay fixture patching |
| tests/fixtures/control_loop_chaos_scenarios.json | MODIFY | Reconcile scenario replay artifacts with budget/objective consistency hardening |
| tests/test_eval_ci_gate.py | MODIFY | Align exit code assertions/messages with current control-loop coupling contract |
| scripts/run_control_loop_chaos_tests.py | MODIFY (if needed) | Keep CLI expectations consistent with fixture/summary behavior |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_control_loop_chaos.py tests/test_eval_ci_gate.py`
2. `pytest tests/test_contracts.py`
3. `PLAN_FILES="<declared files>" .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not relax `control_loop` validation behavior.
- Do not modify runtime control decision semantics to satisfy tests.
- Do not refactor unrelated test modules or runtime modules.

## Dependencies
- Existing replay_result + error_budget_status contract semantics remain authoritative.
