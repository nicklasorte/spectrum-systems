# Plan — BATCH-TLC-01 — 2026-04-06

## Prompt type
PLAN

## Roadmap item
BATCH-TLC-01 (TLC-001)

## Objective
Implement a thin, deterministic top-level conductor that orchestrates existing subsystem seams (PQX/TPA/FRE/RIL/CDE/PRG/SEL), enforces bounded stop conditions, and emits a schema-valid top_level_conductor_run_artifact.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-TLC-01-2026-04-06.md | CREATE | Required PLAN artifact before multi-file BUILD work |
| spectrum_systems/modules/runtime/top_level_conductor.py | CREATE | TLC runtime state-machine implementation |
| contracts/schemas/top_level_conductor_run_artifact.schema.json | CREATE | Contract-first schema for TLC output artifact |
| contracts/examples/top_level_conductor_run_artifact.json | CREATE | Golden-path example for TLC artifact |
| contracts/standards-manifest.json | MODIFY | Register new artifact contract and bump manifest version |
| tests/test_top_level_conductor.py | CREATE | Deterministic orchestration coverage for TLC behavior |
| docs/review-actions/TLC-001-role-boundary-notes-2026-04-06.md | CREATE | Explicit role-boundary documentation for TLC orchestration-only scope |

## Contracts touched
- Create `top_level_conductor_run_artifact` schema at `contracts/schemas/top_level_conductor_run_artifact.schema.json`.
- Register `top_level_conductor_run_artifact` in `contracts/standards-manifest.json` with schema version `1.0.0`.

## Tests that must pass after execution
1. `pytest tests/test_top_level_conductor.py -q`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py -q`
3. `pytest tests/test_module_architecture.py -q`
4. `python scripts/run_contract_enforcement.py`
5. `.codex/skills/contract-boundary-audit/run.sh`
6. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not reimplement PQX/TPA/FRE/RIL/CDE/PRG/SEL subsystem logic.
- Do not modify unrelated runtime modules.
- Do not change control-loop or roadmap policy semantics outside TLC orchestration boundaries.

## Dependencies
- Existing subsystem entrypoints remain authoritative and are consumed as integration seams.
