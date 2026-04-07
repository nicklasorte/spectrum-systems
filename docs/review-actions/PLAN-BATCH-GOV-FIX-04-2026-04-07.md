# Plan — BATCH-GOV-FIX-04 — 2026-04-07

## Prompt type
PLAN

## Roadmap item
BATCH-GOV-FIX-04

## Objective
Add checker-level regression tests that lock external-path evaluate_prompt_file() governance behavior without changing wrapper responsibilities or fail-closed semantics.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| tests/test_governance_prompt_enforcement.py | MODIFY | Add direct evaluate_prompt_file() external-path valid/invalid regression tests and diagnostic assertions. |
| docs/execution_reports/BATCH-GOV-FIX-04_delivery_report.md | CREATE | Record required delivery report for this slice. |
| docs/roadmaps/NEXT_SLICE.md | MODIFY | Add next recommended slice summary per delivery contract. |
| docs/roadmaps/SLICE_HISTORY.md | MODIFY | Append concise history entry for this slice. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_governance_prompt_enforcement.py`
2. `pytest tests/test_run_prompt_with_governance.py`
3. `pytest tests/test_governed_prompt_surface_sync.py`
4. `pytest`

## Scope exclusions
- Do not redesign governance enforcement flow.
- Do not move checker logic into wrapper logic.
- Do not add pytest-specific branches to production code.
- Do not modify governed prompt contract content.

## Dependencies
- recent GOV-FIX-03 behavior remains baseline for wrapper-level external path handling.
