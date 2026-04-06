# Plan — BATCH-GHA-02 — 2026-04-06

## Prompt type
PLAN

## Roadmap item
GHA-002 — GitHub Closure + Continuation Pipeline

## Objective
Implement a bounded GitHub-triggered continuation pipeline that consumes GHA-01 ingestion artifacts, runs CDE closure decisioning, conditionally runs TLC, and emits deterministic terminal-state outputs.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-GHA-02-2026-04-06.md | CREATE | Required plan artifact before multi-file BUILD work |
| PLANS.md | MODIFY | Register active plan entry |
| .github/workflows/closure_continuation_pipeline.yml | CREATE | Add GitHub-triggered closure + continuation pipeline workflow |
| spectrum_systems/modules/runtime/github_closure_continuation.py | CREATE | Add thin adapter that normalizes GHA-01 outputs and orchestrates CDE/TLC handoff |
| tests/test_github_closure_continuation.py | CREATE | Validate adapter behavior, guardrails, and deterministic outputs |
| tests/test_closure_continuation_pipeline_workflow.py | CREATE | Validate workflow trigger wiring and required execution steps |
| tests/fixtures/github_events/workflow_run_review_trigger_success.json | CREATE | Deterministic workflow_run fixture for continuation tests |

## Contracts touched
None.

## Tests that must pass after execution

1. `pytest tests/test_github_closure_continuation.py`
2. `pytest tests/test_closure_continuation_pipeline_workflow.py`
3. `pytest tests/test_contracts.py`
4. `pytest tests/test_module_architecture.py`

## Scope exclusions

- Do not modify existing CDE decision rules.
- Do not modify existing TLC orchestration state machine logic.
- Do not introduce any new orchestrator or autonomy loop.
- Do not add direct execution paths outside PQX.

## Dependencies

- GHA-01 review-trigger ingestion outputs must remain the source of downstream continuation inputs.
- Existing CDE and TLC modules must remain authoritative decision/orchestration systems.
