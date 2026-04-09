# Plan — BATCH-GHA-PR-AUTOFIX — 2026-04-09

## Prompt type
BUILD

## Roadmap item
BATCH-GHA-PR-AUTOFIX — Governed PR autofix path for failed `review-artifact-validation` runs.

## Objective
Implement a fail-closed, repo-native PR autofix entrypoint and GitHub workflow transport that preserves System Registry ownership boundaries and enforces mandatory pre-push validation replay.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| `.github/workflows/pr-autofix-review-artifact-validation.yml` | CREATE | Add workflow-run transport that detects failed `review-artifact-validation`, gathers logs, and invokes repo-native governed entrypoint. |
| `spectrum_systems/modules/runtime/github_pr_autofix_review_artifact_validation.py` | CREATE | Add repo-native governed execution path (AEX→TLC→TPA→PQX with SEL fail-closed enforcement and pre-push replay gate). |
| `docs/architecture/pr_autofix_review_artifact_validation.md` | CREATE | Document role ownership mapping, guardrails, fail-closed conditions, and security model for this governed path. |
| `tests/test_pr_autofix_review_artifact_validation_workflow.py` | CREATE | Validate workflow trigger conditions, same-repo guardrails, and repo-native entrypoint invocation. |
| `tests/test_github_pr_autofix_review_artifact_validation.py` | CREATE | Validate fail-closed artifact invariants and mandatory replay gate behavior in entrypoint logic. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_pr_autofix_review_artifact_validation_workflow.py tests/test_github_pr_autofix_review_artifact_validation.py`

## Scope exclusions
- Do not implement a direct GitHub Action-side repair executor.
- Do not add any non-governed bypass path that writes to the repository without AEX/TLC/TPA lineage.
- Do not modify unrelated workflows or runtime modules.

## Dependencies
- `README.md` and `docs/architecture/system_registry.md` remain canonical ownership authorities.
