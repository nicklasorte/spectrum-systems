# Plan — REVIEW-FIX-LOOP-36-EXPLICIT — 2026-04-11

## Prompt type
BUILD

## Roadmap item
REVIEW-FIX-LOOP-36-EXPLICIT

## Objective
Implement a deterministic, artifact-first 36-step multi-pass review/fix/replay/promotion/pre-merge hardening run with strict serial checkpoints and explicit ownership boundaries.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-REVIEW-FIX-LOOP-36-EXPLICIT-2026-04-11.md | CREATE | Required written plan before multi-file governed change |
| scripts/run_review_fix_loop_36_explicit.py | CREATE | Deterministic generator for 36-step governed artifacts, checkpoints, and trace |
| tests/test_review_fix_loop_36_explicit.py | CREATE | Deterministic validation for required artifacts, checkpoints, and ownership boundaries |
| artifacts/review_fix_loop_36_explicit/* | CREATE | Governed run outputs including all required artifacts |
| artifacts/rdx_runs/REVIEW-FIX-LOOP-36-EXPLICIT-artifact-trace.json | CREATE | RDX trace linkage for the governed batch |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_review_fix_loop_36_explicit.py`

## Scope exclusions
- Do not modify canonical ownership definitions in `docs/architecture/system_registry.md`.
- Do not modify contract schemas or standards manifest.
- Do not refactor unrelated scripts/tests.

## Dependencies
- `README.md` and `docs/architecture/system_registry.md` remain canonical authority.
