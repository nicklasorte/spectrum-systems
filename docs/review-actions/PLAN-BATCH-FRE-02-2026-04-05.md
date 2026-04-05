# Plan — BATCH-FRE-02 — 2026-04-05

## Prompt type
PLAN

## Roadmap item
BATCH-FRE-02 (FRE-004/FRE-005)

## Objective
Implement a deterministic repair prompt generator that converts a valid failure diagnosis artifact into a minimal, constrained, validation-ready repair prompt artifact backed by a new registered contract.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-FRE-02-2026-04-05.md | CREATE | Required plan-first artifact for this multi-file build slice. |
| spectrum_systems/modules/runtime/repair_prompt_generator.py | CREATE | FRE-004 runtime generator implementation and deterministic template mapping logic. |
| contracts/schemas/repair_prompt_artifact.schema.json | CREATE | FRE-005 schema contract for generated repair prompt artifacts. |
| contracts/examples/repair_prompt_artifact.json | CREATE | Golden-path example for the new repair prompt artifact contract. |
| contracts/standards-manifest.json | MODIFY | Register repair_prompt_artifact and bump standards manifest version metadata. |
| tests/test_repair_prompt_generator.py | CREATE | Deterministic coverage for mappings, constraints, validation command inclusion, and fail-closed behavior. |

## Contracts touched
- `contracts/schemas/repair_prompt_artifact.schema.json` (new)
- `contracts/standards-manifest.json` (version bump + registration)

## Tests that must pass after execution
1. `pytest tests/test_repair_prompt_generator.py -q`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py -q`
3. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not implement or execute repairs; only generate repair prompts.
- Do not modify failure diagnosis classification logic beyond consumption requirements.
- Do not redesign prompt queue workflows or existing prompt_queue repair prompt artifacts.
- Do not weaken contract strictness, control/preflight behavior, or determinism constraints.

## Dependencies
- `docs/review-actions/PLAN-BATCH-FRE-01-2026-04-05.md` must be complete enough to provide failure diagnosis artifact contract and deterministic diagnosis outputs.
