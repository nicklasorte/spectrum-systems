# Plan — BATCH-PFG-AFX-A — 2026-04-10

## Prompt type
BUILD

## Roadmap item
BATCH-PFG-AFX-A — PreFlight Gate + Canonical Validation + Repair Artifact Spine

## Objective
Make governed autofix progression fail closed unless TLC-integrated preflight passes, route CI/autofix validation through one canonical entrypoint, and enforce an artifact spine before PR/push decisions.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| `scripts/run_review_artifact_validation.py` | CREATE | Canonical validation entrypoint shared by CI and autofix replay |
| `.github/workflows/review-artifact-validation.yml` | MODIFY | Route CI through canonical validation entrypoint |
| `spectrum_systems/modules/runtime/github_pr_autofix_review_artifact_validation.py` | MODIFY | Enforce preflight artifact gate and required artifact spine before commit/push |
| `tests/test_github_pr_autofix_review_artifact_validation.py` | MODIFY | Add required fail-closed + consistency + artifact spine tests |
| `docs/reviews/pfg_afx_a_redteam.md` | CREATE | Targeted red-team review for new seam |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_github_pr_autofix_review_artifact_validation.py`
2. `python scripts/run_review_artifact_validation.py --repo-root . --output-json /tmp/review_validation.json --allow-full-pytest`

## Scope exclusions
- Do not redesign orchestration/runtime systems beyond this seam.
- Do not add new role ownership definitions in governance docs.
- Do not weaken existing fail-closed behavior.

## Dependencies
- Existing governed autofix runtime entry (`github_pr_autofix_review_artifact_validation`) remains authoritative for repo mutations.
