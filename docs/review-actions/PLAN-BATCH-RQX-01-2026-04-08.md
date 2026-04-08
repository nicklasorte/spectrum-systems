# Plan — BATCH-RQX-01 — 2026-04-08

## Prompt type
BUILD

## Roadmap item
BATCH-RQX-01

## Objective
Implement a bounded repo-native RQX review loop that validates a strict review request artifact, emits structured review result and merge readiness artifacts, and writes a markdown review in `docs/reviews/` derived from structured output.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-RQX-01-2026-04-08.md | CREATE | Required plan-first declaration for multi-file BUILD slice. |
| contracts/schemas/review_request_artifact.schema.json | CREATE | Canonical strict input contract for RQX bounded review requests. |
| contracts/schemas/review_result_artifact.schema.json | CREATE | Canonical strict structured review output contract. |
| contracts/schemas/review_merge_readiness_artifact.schema.json | CREATE | Canonical strict machine-readable merge readiness verdict contract. |
| contracts/examples/review_request_artifact.json | CREATE | Deterministic golden-path input example for RQX. |
| contracts/examples/review_result_artifact.json | CREATE | Deterministic golden-path output example for RQX review results. |
| contracts/examples/review_merge_readiness_artifact.json | CREATE | Deterministic golden-path output example for merge readiness verdicts. |
| contracts/standards-manifest.json | MODIFY | Publish new artifact contracts and bump manifest version. |
| spectrum_systems/modules/review_queue_executor.py | CREATE | Repo-native RQX module entrypoint implementing bounded review loop. |
| tests/test_review_queue_executor.py | CREATE | Deterministic tests covering validation, output artifacts, markdown derivation, and bounded behavior. |

## Contracts touched
- NEW: `review_request_artifact` (1.0.0)
- NEW: `review_result_artifact` (1.0.0)
- NEW: `review_merge_readiness_artifact` (1.0.0)
- UPDATE: `contracts/standards-manifest.json` version bump + contract registrations

## Tests that must pass after execution
1. `pytest tests/test_review_queue_executor.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not implement automatic repair/fix execution.
- Do not add recursive or autonomous self-healing loops.
- Do not redesign PQX orchestration or broader enforcement architecture.
- Do not create a new repository or non-module framework.

## Dependencies
- Existing PQX run/batch artifact conventions and contract loader in `spectrum_systems.contracts`.
