# Plan — BATCH-AEX-FIX-06 — 2026-04-09

## Prompt type
PLAN

## Roadmap item
BATCH-AEX-FIX-06

## Objective
Make PQX execution boundary require repo-write lineage based on actual repo-write capability and enforce replay protection at that same boundary.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| spectrum_systems/modules/runtime/pqx_slice_runner.py | MODIFY | Enforce lineage by repo-controlled runtime path capability and enable replay protection at boundary validation call. |
| spectrum_systems/modules/runtime/pqx_sequence_runner.py | MODIFY | Keep boundary authoritative by disabling replay-token consumption in upstream sequence precheck validation. |
| tests/test_pqx_slice_runner.py | MODIFY | Add direct boundary invariant tests for capability-based lineage enforcement and replay rejection. |
| tests/test_codex_to_pqx_wrapper.py | MODIFY | Add one public caller-path regression test proving non_repo_write declaration cannot bypass repo-capable boundary. |
| tests/test_cycle_runner.py | MODIFY | Keep cycle reentry coverage aligned with replay-protected lineage by refreshing lineage identifiers before replay-sensitive reentry. |
| docs/architecture/foundation_pqx_eval_control.md | MODIFY | Keep architecture note truthful about capability-based boundary enforcement and replay protection. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_pqx_slice_runner.py`
2. `pytest tests/test_codex_to_pqx_wrapper.py`

## Scope exclusions
- Do not redesign PQX architecture or add a new subsystem.
- Do not add new authentication machinery.
- Do not refactor unrelated callers.
- Do not modify contract schemas.

## Dependencies
- None.
