# Plan — BATCH-GHA-01 — 2026-04-06

## Prompt type
PLAN

## Roadmap item
GHA-001

## Objective
Implement a thin GitHub-triggered ingestion pipeline that normalizes review/comment/manual events into governed repo-native artifacts and executes deterministic RIL structuring outputs without adding closure, continuation, or repair decisions.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-GHA-01-2026-04-06.md | CREATE | Required PLAN artifact before multi-file BUILD execution. |
| .github/workflows/review_trigger_pipeline.yml | CREATE | Add minimal GitHub event workflow for review ingestion + RIL automation. |
| spectrum_systems/modules/runtime/github_review_ingestion.py | CREATE | Implement thin GitHub ingestion adapter and RIL execution wiring. |
| tests/test_github_review_ingestion.py | CREATE | Add deterministic adapter and fail-closed coverage. |
| tests/test_review_trigger_pipeline_workflow.py | CREATE | Validate workflow trigger and guardrail wiring. |
| tests/fixtures/github_events/pull_request_review_submitted.json | CREATE | Deterministic fixture for review-submitted trigger normalization tests. |
| tests/fixtures/github_events/issue_comment_pr_command.json | CREATE | Deterministic fixture for PR issue_comment command trigger tests. |
| tests/fixtures/github_events/workflow_dispatch_manual.json | CREATE | Deterministic fixture for manual dispatch input normalization tests. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_github_review_ingestion.py tests/test_review_trigger_pipeline_workflow.py`

## Scope exclusions
- Do not add CDE/TLC continuation/closure logic.
- Do not implement repairs or execution decisions.
- Do not alter existing RIL interpretation logic.
- Do not add unrelated workflows or repository refactors.

## Dependencies
- Existing RIL modules (`review_parsing_engine`, `review_signal_classifier`, `review_signal_consumer`, `review_projection_adapter`, `review_consumer_wiring`) remain authoritative and are reused as-is.
