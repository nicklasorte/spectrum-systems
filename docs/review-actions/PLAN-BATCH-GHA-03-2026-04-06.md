# Plan — BATCH-GHA-03 — 2026-04-06

## Prompt type
PLAN

## Roadmap item
GHA-003 — Read-Only PR Feedback Publisher

## Objective
Add a deterministic, read-only PR feedback publisher that formats governed continuation outputs into a non-authoritative PR comment and posts it idempotently from the closure continuation workflow.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-GHA-03-2026-04-06.md | CREATE | Required plan artifact before multi-file BUILD work |
| PLANS.md | MODIFY | Register active plan entry |
| .github/workflows/closure_continuation_pipeline.yml | MODIFY | Add read-only PR feedback publishing step with fail-closed guards and idempotent update behavior |
| spectrum_systems/modules/runtime/github_pr_feedback.py | CREATE | Add deterministic comment builder with strict non-interpretive formatting and validation |
| tests/test_github_pr_feedback.py | CREATE | Validate deterministic format, fail-closed behavior, and absence of interpretation logic |

## Contracts touched
None.

## Tests that must pass after execution

1. `pytest tests/test_github_pr_feedback.py`
2. `pytest tests/test_closure_continuation_pipeline_workflow.py`
3. `pytest tests/test_contracts.py`
4. `pytest tests/test_module_architecture.py`

## Scope exclusions

- Do not modify CDE decision rules.
- Do not modify TLC orchestration semantics.
- Do not introduce any execution/decision authority in PR feedback output.
- Do not add network behavior to test suite.

## Dependencies

- GHA-002 continuation output (`continuation_result.json` + emitted artifacts) remains the sole source for PR feedback content.
- Existing closure_decision_artifact and top_level_conductor_run_artifact contracts remain authoritative.
