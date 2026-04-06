# Plan — BATCH-TLC-02 — 2026-04-06

## Prompt type
PLAN

## Roadmap item
TLC-002

## Objective
Wire top-level conductor to real subsystem entrypoints (PQX/TPA/FRE/RIL/CDE/PRG/SEL) with fail-closed contract validation at each handoff and prove behavior with deterministic golden and blocked integration runs.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-TLC-02-2026-04-06.md | CREATE | Required plan artifact before multi-file BUILD work. |
| spectrum_systems/modules/runtime/top_level_conductor.py | MODIFY | Replace test seams with real adapter wiring and boundary validation/lineage recording. |
| tests/test_top_level_conductor.py | MODIFY | Add deterministic golden + blocked integration runs and handoff/SEL/determinism assertions. |

## Contracts touched
None.

## Tests that must pass after execution

1. `pytest tests/test_top_level_conductor.py`
2. `pytest tests/test_contracts.py`

## Scope exclusions

- Do not modify PQX/TPA/FRE/RIL/CDE/PRG/SEL subsystem internals.
- Do not introduce new policy/decision logic in TLC.
- Do not add new modules or repositories.
- Do not bypass SEL on any TLC boundary.

## Dependencies

- Existing subsystem entrypoints and contract schemas in `contracts/schemas/` remain authoritative and must be consumed as-is.
