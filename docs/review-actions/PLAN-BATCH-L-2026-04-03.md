# Plan — BATCH-L — 2026-04-03

## Prompt type
PLAN

## Roadmap item
BATCH-L — Failure Learning Loop

## Objective
Add deterministic failure-pattern recording and threshold-based eval auto-generation so repeated failures become enforceable prevention gates.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-L-2026-04-03.md | CREATE | Required plan-first governance artifact for this multi-file BUILD slice. |
| PLANS.md | MODIFY | Register the new BATCH-L plan in active plans table. |
| contracts/schemas/failure_pattern_record.schema.json | CREATE | Contract-first schema for failure_pattern_record artifact required by BATCH-L. |
| contracts/examples/failure_pattern_record.json | CREATE | Golden-path example for new failure_pattern_record contract. |
| contracts/standards-manifest.json | MODIFY | Publish failure_pattern_record contract and bump manifest version metadata. |
| spectrum_systems/modules/runtime/evaluation_auto_generation.py | MODIFY | Implement deterministic normalization, failure pattern record creation, and threshold-based eval case generation/linking. |
| tests/test_evaluation_auto_generation.py | MODIFY | Add deterministic and threshold/duplicate prevention tests for failure-pattern learning loop. |
| tests/test_control_loop.py | MODIFY | Validate generated failure-pattern evals are consumable by control loop and enforce future-run blocking behavior. |

## Contracts touched
- `contracts/schemas/failure_pattern_record.schema.json` (new)
- `contracts/standards-manifest.json` (version bump + contract registration)

## Tests that must pass after execution
1. `pytest tests/test_evaluation_auto_generation.py tests/test_control_loop.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`

## Scope exclusions
- Do not refactor unrelated runtime modules.
- Do not alter roadmap authority files.
- Do not change CI workflows.

## Dependencies
- Existing AG-05 failure eval generation and CL control-loop enforcement remain the base integration path.
