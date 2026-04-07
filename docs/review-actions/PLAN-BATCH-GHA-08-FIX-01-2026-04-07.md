# Plan — BATCH-GHA-08-FIX-01 — 2026-04-07

## Prompt type
PLAN

## Roadmap item
BATCH-GHA-08-FIX-01

## Objective
Enforce branch update permission strictly from terminal-state truth so branch updates are only allowed when terminal state is `ready_for_merge`.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-GHA-08-FIX-01-2026-04-07.md | CREATE | Required PLAN artifact for governed fix execution. |
| spectrum_systems/modules/runtime/github_closure_continuation.py | MODIFY | Apply minimal branch-update policy correction at continuation summary boundary. |
| tests/test_github_closure_continuation.py | MODIFY | Align assertions to terminal-state-authoritative branch-update policy invariant. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_github_closure_continuation.py -q`
2. `pytest tests/test_pre_pr_repair_loop.py -q`
3. `pytest tests/test_top_level_conductor.py -q`
4. `python scripts/run_contract_preflight.py --base-ref "e5b9f135b21ab5d2b3509c44c0d5cc82450b55f1" --head-ref "$(git rev-parse HEAD)" --output-dir outputs/contract_preflight`
5. `PLAN_FILES='docs/review-actions/PLAN-BATCH-GHA-08-FIX-01-2026-04-07.md spectrum_systems/modules/runtime/github_closure_continuation.py' .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not change FRE diagnosis logic.
- Do not modify TLC or CDE semantics unless strictly required.
- Do not broaden branch update permissions.
- Do not modify schemas or contracts.
- Do not introduce new systems or acronyms.

## Dependencies
- Existing GHA-08 behavior and tests must remain intact.
