# Plan — BATCH-RQX-02 — 2026-04-08

## Prompt type
BUILD

## Roadmap item
BATCH-RQX-02

## Objective
Extend the bounded RQX review loop to emit at most one machine-readable bounded `review_fix_slice_artifact` when verdict is `fix_required`, keep RQX fail-closed and non-executing, and wire canonical registry ownership/boundary definitions for RQX.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-RQX-02-2026-04-08.md | CREATE | Required plan-first declaration for this multi-file bounded BUILD slice. |
| contracts/schemas/review_fix_slice_artifact.schema.json | CREATE | Canonical strict contract for bounded RQX fix-slice request emission. |
| contracts/examples/review_fix_slice_artifact.json | CREATE | Deterministic golden example for the new fix-slice artifact. |
| contracts/standards-manifest.json | MODIFY | Register new contract and bump manifest version metadata. |
| spectrum_systems/modules/review_queue_executor.py | MODIFY | Emit exactly one fix slice for `fix_required` verdicts; preserve fail-closed bounded behavior and markdown alignment. |
| tests/test_review_queue_executor.py | MODIFY | Add bounded fix-slice emission tests and schema validation coverage. |
| docs/architecture/system_registry.md | MODIFY | Register RQX with canonical ownership, anti-duplication constraints, interactions, and invariant updates. |

## Contracts touched
- NEW: `review_fix_slice_artifact` (1.0.0)
- UPDATE: `contracts/standards-manifest.json` version bump + contract registration

## Tests that must pass after execution
1. `pytest tests/test_review_queue_executor.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not execute emitted fix slices.
- Do not create recursive review→fix→review automation.
- Do not broaden RQX into FRE, RIL, SEL, CDE, or PQX ownership.
- Do not redesign architecture outside thin registry wiring and bounded artifact handoff.
