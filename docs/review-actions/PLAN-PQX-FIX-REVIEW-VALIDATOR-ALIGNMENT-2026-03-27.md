# Plan — PQX-FIX Review Validator Alignment — 2026-03-27

## Prompt type
PLAN

## Roadmap item
PQX-FIX — Review Artifact Validator Alignment

## Objective
Unify repository review-artifact validation around the canonical `contracts/schemas/review_artifact.schema.json` path so repo-level and pairwise validation produce consistent pass/fail outcomes.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| scripts/validate_review_artifacts.py | MODIFY | Delegate to canonical pairwise validator logic and enforce JSON/Markdown pair checks. |
| docs/reviews/README.md | MODIFY | Document one authoritative validation flow and repo-level wrapper behavior. |
| tests/test_control_loop_hardening.py | MODIFY | Align existing validator script tests to canonical review_artifact contract and markdown-pair enforcement. |
| tests/test_review_artifact_repo_validation.py | CREATE | Add coverage for repo-level validator success/failure and missing markdown pair handling. |
| docs/reviews/2026-03-27-review-validator-alignment.md | CREATE | Record authoritative validator decision and alignment rationale. |
| docs/review-actions/2026-03-27-review-validator-alignment-actions.md | CREATE | Track governance actions, deprecations, and follow-ups. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest -q`
2. `python scripts/validate_review_artifacts.py`

## Scope exclusions
- Do not modify `contracts/schemas/review_artifact.schema.json` unless strict compatibility break is discovered.
- Do not alter unrelated review artifacts.
- Do not relax schema validation requirements.

## Dependencies
- Existing governed artifacts in `docs/reviews/` must remain valid under the canonical pairwise validator.
