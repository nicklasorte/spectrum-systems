# Plan — PR Autofix Hardening — 2026-04-09

## Prompt type
VALIDATE

## Roadmap item
GHA-008 pre-PR bounded repair-loop behavior hardening

## Objective
Harden the PR autofix execution path so repo mutation occurs only through explicit governed artifacts, deterministic bounded repair execution, and fail-closed validation replay before any push.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PR-AUTOFIX-HARDENING-2026-04-09.md | CREATE | Required written plan for multi-file hardening pass. |
| .github/workflows/pr-autofix-review-artifact-validation.yml | MODIFY | Keep workflow as transport-only and enforce explicit skip behavior + token wiring. |
| spectrum_systems/modules/runtime/github_pr_autofix_review_artifact_validation.py | MODIFY | Strengthen governed autofix execution, replay gating, and fail-closed mutation/push controls. |
| tests/test_github_pr_autofix_review_artifact_validation.py | MODIFY | Add deterministic scenario coverage for hard-failure, unfixable, replay mismatch, and token controls. |
| tests/test_pr_autofix_review_artifact_validation_workflow.py | MODIFY | Verify workflow boundaries, explicit fork skip behavior, and non-GITHUB_TOKEN push behavior. |
| docs/architecture/pr_autofix_review_artifact_validation.md | MODIFY | Keep governed behavior explicit and aligned with hardened execution path. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_github_pr_autofix_review_artifact_validation.py`
2. `pytest tests/test_pr_autofix_review_artifact_validation_workflow.py`

## Scope exclusions
- Do not introduce new subsystems or role ownership definitions.
- Do not change `review-artifact-validation` workflow semantics beyond replay equivalence requirements.
- Do not broaden autofix beyond bounded deterministic execution.

## Dependencies
- Canonical ownership remains `README.md` + `docs/architecture/system_registry.md`.
