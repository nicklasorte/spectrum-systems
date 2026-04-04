# Plan — BATCH-CYCLE-RUNNER — 2026-04-04

## Prompt type
PLAN

## Roadmap item
BATCH-CYCLE-RUNNER

## Objective
Add a thin, deterministic, fail-closed runner that consumes `next_cycle_decision` + `next_cycle_input_bundle`, executes at most one governed next cycle when explicitly allowed, and emits a strict `cycle_runner_result` artifact.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-CYCLE-RUNNER-2026-04-04.md | CREATE | Plan-first artifact required before multi-file BUILD work. |
| PLANS.md | MODIFY | Register this batch plan in Active plans. |
| contracts/schemas/cycle_runner_result.schema.json | CREATE | Define strict schema for new governed artifact. |
| contracts/examples/cycle_runner_result.json | CREATE | Provide contract-valid golden-path example. |
| contracts/standards-manifest.json | MODIFY | Add `cycle_runner_result` and bump standards manifest version. |
| spectrum_systems/modules/runtime/next_governed_cycle_runner.py | CREATE | Implement bounded one-step runner logic and result artifact emission. |
| scripts/run_next_governed_cycle.py | CREATE | Add thin CLI entrypoint for one-step governed cycle execution. |
| docs/runbooks/cycle_runner.md | MODIFY | Document operator flow including bounded runner and `cycle_runner_result`. |
| tests/test_next_governed_cycle_runner.py | CREATE | Add targeted runner and CLI behavior tests. |
| tests/test_contracts.py | MODIFY | Include `cycle_runner_result` in contract example validation coverage. |

## Contracts touched
- `cycle_runner_result` (new)
- `standards_manifest` version bump + new contract registration

## Tests that must pass after execution
1. `pytest tests/test_next_governed_cycle_runner.py`
2. `pytest tests/test_system_cycle_operator.py`
3. `pytest tests/test_system_mvp_validation.py`
4. `pytest tests/test_contracts.py`
5. `pytest tests/test_contract_enforcement.py`
6. `python scripts/run_contract_enforcement.py`
7. `PLAN_FILES="docs/review-actions/PLAN-BATCH-CYCLE-RUNNER-2026-04-04.md PLANS.md contracts/schemas/cycle_runner_result.schema.json contracts/examples/cycle_runner_result.json contracts/standards-manifest.json spectrum_systems/modules/runtime/next_governed_cycle_runner.py scripts/run_next_governed_cycle.py docs/runbooks/cycle_runner.md tests/test_next_governed_cycle_runner.py tests/test_contracts.py" .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign `run_system_cycle` internals or multi-cycle orchestration architecture.
- Do not add recursive or scheduler-driven continuation behavior.
- Do not modify unrelated contracts or runtime modules outside runner wiring needs.

## Dependencies
- Existing `next_cycle_decision` and `next_cycle_input_bundle` contracts and `run_system_cycle` operator seam must remain authoritative.
