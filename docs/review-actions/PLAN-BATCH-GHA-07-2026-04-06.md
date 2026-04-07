# Plan — BATCH-GHA-07 — 2026-04-06

## Prompt type
PLAN

## Roadmap item
BATCH-GHA-07 — Roadmap Execution Bridge (Artifact → Execution)

## Objective
Convert `roadmap_two_step_artifact` into deterministic, bounded TLC-orchestrated PQX execution with explicit fail-closed governance artifacts.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-GHA-07-2026-04-06.md | CREATE | Required plan artifact before multi-file BUILD/WIRE work. |
| PLANS.md | MODIFY | Register newly created plan in active plans table. |
| contracts/schemas/roadmap_step_execution_artifact.schema.json | CREATE | Define governed contract for per-step execution results. |
| contracts/examples/roadmap_step_execution_artifact.json | CREATE | Provide deterministic golden-path contract example. |
| contracts/standards-manifest.json | MODIFY | Add canonical contract pin for `roadmap_step_execution_artifact`. |
| spectrum_systems/modules/runtime/roadmap_execution_adapter.py | CREATE | Implement roadmap→execution conversion adapter and deterministic plan builder. |
| spectrum_systems/modules/runtime/top_level_conductor.py | MODIFY | Add `run_from_roadmap` orchestration entry path through TLC→PQX loop. |
| tests/test_roadmap_execution.py | CREATE | Add integration and failure-mode coverage for roadmap execution bridge. |
| tests/test_top_level_conductor.py | MODIFY | Add TLC roadmap-entry-path integration coverage. |

## Contracts touched
- Create `roadmap_step_execution_artifact` schema `1.0.0`.
- Add `roadmap_step_execution_artifact` entry in `contracts/standards-manifest.json`.

## Tests that must pass after execution
1. `pytest tests/test_roadmap_execution.py`
2. `pytest tests/test_top_level_conductor.py`
3. `pytest tests/test_contracts.py`
4. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not modify roadmap generation logic.
- Do not change PQX internals outside TLC invocation paths.
- Do not alter CDE closure authority semantics.
- Do not bypass system registry or SEL checks.

## Dependencies
- Existing `roadmap_two_step_artifact` contract and example must remain authoritative input.
- Existing TLC subsystem boundaries (SEL/PQX/TPA/FRE/RIL/CDE/PRG) remain authoritative.
