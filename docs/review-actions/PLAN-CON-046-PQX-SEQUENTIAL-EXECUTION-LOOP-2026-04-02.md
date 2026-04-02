# Plan — CON-046 — 2026-04-02

## Prompt type
PLAN

## Roadmap item
CON-046 — PQX Sequential Execution Loop (Control-Loop Native MVP)

## Objective
Implement a deterministic sequential PQX orchestration loop that reuses existing wrapper, eval, decision, and enforcement seams and emits a fail-closed execution trace artifact.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CON-046-PQX-SEQUENTIAL-EXECUTION-LOOP-2026-04-02.md | CREATE | Required PLAN artifact before multi-file BUILD work |
| PLANS.md | MODIFY | Register active CON-046 plan in plan ledger |
| spectrum_systems/modules/runtime/pqx_sequential_loop.py | CREATE | Implement deterministic sequential orchestration loop |
| scripts/run_pqx_sequence.py | CREATE | Add thin CLI entrypoint for sequence execution |
| tests/test_pqx_sequential_loop.py | CREATE | Add deterministic coverage for allow/block/review/fail-closed paths |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest -q tests/test_pqx_slice_runner.py`
2. `pytest -q tests/test_contract_preflight.py`
3. `pytest -q tests/test_contracts.py`
4. `pytest -q tests/test_contract_enforcement.py`
5. `pytest -q tests/test_pqx_sequential_loop.py`
6. `python scripts/run_contract_enforcement.py`
7. `python scripts/run_contract_preflight.py --help`

## Scope exclusions
- Do not add new evaluation logic.
- Do not add new control-decision logic.
- Do not modify existing control loop, enforcement engine, or slice runner semantics.
- Do not add parallel execution paths.

## Dependencies
- CON-038 wrapper seam must remain authoritative for wrapper payload reuse.
- CON-039 required-context enforcement remains authoritative for fail-closed wrapper/context checks.
