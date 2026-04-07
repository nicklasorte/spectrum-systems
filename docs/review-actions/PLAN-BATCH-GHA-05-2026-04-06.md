# Plan — BATCH-GHA-05 — 2026-04-06

## Prompt type
PLAN

## Roadmap item
GHA-005 — Roadmap Draft + Approval Gate

## Objective
Add a deterministic two-phase roadmap workflow where `/roadmap-draft` emits a read-only, schema-valid roadmap artifact and `/roadmap-approve` is required to feed that artifact into governed continuation through CDE → TLC.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-GHA-05-2026-04-06.md | CREATE | Required PLAN artifact before multi-file BUILD execution |
| .github/workflows/review_trigger_pipeline.yml | MODIFY | Add new command guardrails and draft PR feedback publishing path |
| .github/workflows/closure_continuation_pipeline.yml | MODIFY | Gate continuation on approval command and enforce draft-only no-continuation path |
| spectrum_systems/modules/runtime/github_roadmap_builder.py | MODIFY | Support deterministic `/roadmap-draft` bounded roadmap build contract |
| spectrum_systems/modules/runtime/github_review_ingestion.py | MODIFY | Add `/roadmap-draft` + `/roadmap-approve` intake routing, draft storage, and approval context |
| spectrum_systems/modules/runtime/github_closure_continuation.py | MODIFY | Resolve/validate approved roadmap artifact and fail closed on missing/stale inputs |
| spectrum_systems/modules/runtime/github_pr_feedback.py | MODIFY | Add read-only roadmap draft PR comment type |
| tests/test_roadmap_draft_and_approval.py | CREATE | Required GHA-005 deterministic/guardrail test coverage |
| tests/test_roadmap_trigger_pipeline.py | MODIFY | Align workflow command-marker assertions with new commands |
| tests/test_github_review_ingestion.py | MODIFY | Validate new draft/approval command normalization and artifact behavior |
| tests/test_github_closure_continuation.py | MODIFY | Validate approval artifact resolution and fail-closed behavior |
| tests/test_github_pr_feedback.py | MODIFY | Validate roadmap draft PR comment rendering |
| tests/test_github_roadmap_builder.py | MODIFY | Align deterministic roadmap builder command marker coverage |

## Contracts touched
None (reuses existing `roadmap_two_step_artifact` and existing governed artifact schemas).

## Tests that must pass after execution
1. `pytest tests/test_roadmap_draft_and_approval.py`
2. `pytest tests/test_github_review_ingestion.py tests/test_github_closure_continuation.py tests/test_github_pr_feedback.py`
3. `pytest tests/test_roadmap_trigger_pipeline.py tests/test_review_trigger_pipeline_workflow.py`

## Scope exclusions
- Do not add new autonomous planners, executors, or orchestration subsystems.
- Do not bypass or replace CDE/TLC/PQX boundaries.
- Do not modify unrelated contracts, module layout, or roadmap execution authority files.

## Dependencies
- Existing GHA-002/GHA-003 governed ingestion + continuation pathways remain the continuation backbone.
