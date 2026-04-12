# Plan — CERTIFICATION-JUDGMENT-40-EXPLICIT — 2026-04-11

## Prompt type
PLAN

## Roadmap item
CERTIFICATION-JUDGMENT-40-EXPLICIT

## Objective
Implement a strict-serial 40-step execution artifact generator with hard checkpoints, required output artifacts, and deterministic validation coverage for certification and judgment governance.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CERTIFICATION-JUDGMENT-40-EXPLICIT-2026-04-11.md | CREATE | Required plan-first declaration for multi-file scope |
| scripts/run_certification_judgment_40_explicit.py | CREATE | Deterministic serial execution script that emits all 40 required artifacts and checkpoint validations |
| tests/test_certification_judgment_40_explicit.py | CREATE | Deterministic validation coverage for required artifacts, checkpoints, and ownership boundaries |
| artifacts/certification_judgment_40_explicit/*.json | CREATE | Materialized execution artifacts required by this batch |
| artifacts/rdx_runs/CERTIFICATION-JUDGMENT-40-EXPLICIT-artifact-trace.json | CREATE | Serial execution trace output |

## Contracts touched
None.

## Tests that must pass after execution

1. `pytest tests/test_certification_judgment_40_explicit.py`
2. `python scripts/run_certification_judgment_40_explicit.py`

## Scope exclusions

- Do not modify canonical role ownership definitions in `docs/architecture/system_registry.md`.
- Do not modify contract schemas or `contracts/standards-manifest.json`.
- Do not refactor unrelated scripts or tests.

## Dependencies

- `README.md` and `docs/architecture/system_registry.md` remain the canonical authority surfaces for this batch.
