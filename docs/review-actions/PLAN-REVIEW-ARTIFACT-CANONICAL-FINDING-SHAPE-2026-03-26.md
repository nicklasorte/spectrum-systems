# Plan — REVIEW-ARTIFACT-CANONICAL-FINDING-SHAPE — 2026-03-26

## Prompt type
PLAN

## Roadmap item
Contract consistency maintenance (active roadmap-aligned contract hardening)

## Objective
Align review_artifact contract examples, review checkpoint artifact, and contract-focused tests to one canonical structured finding shape defined by `contracts/schemas/review_artifact.schema.json`.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| contracts/examples/review_artifact.json | MODIFY | Ensure example strictly uses canonical review_artifact fields and enums. |
| contracts/examples/review_artifact.example.json | MODIFY | Keep paired example artifact aligned with canonical schema shape. |
| docs/reviews/2026-03-26-core-loop-checkpoint-review.json | MODIFY | Regenerate/align checkpoint review artifact to canonical shape and valid related plan pattern. |
| tests/test_review_artifact_contract.py | MODIFY | Update contract test assertions to require canonical finding fields and reject legacy assumptions. |

## Contracts touched
None (schema treated as authoritative; no schema changes planned).

## Tests that must pass after execution
1. `pytest tests/test_review_artifact_contract.py -q`
2. `pytest tests/test_review_examples_valid.py -q`
3. `pytest tests/test_review_contract_schema.py -q`

## Scope exclusions
- Do not change `contracts/schemas/review_artifact.schema.json` unless a compelling contract contradiction is discovered.
- Do not modify unrelated review schemas (`standards/review-contract.schema.json`, `design-reviews/*`).
- Do not refactor non-contract runtime modules.

## Dependencies
- None.
