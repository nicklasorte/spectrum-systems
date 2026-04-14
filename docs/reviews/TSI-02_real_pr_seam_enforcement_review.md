# TSI-02 Real PR Seam Enforcement Review

## 1. Real PR seam identified
The authoritative PR pass/fail seam is the `contract-preflight` job in `.github/workflows/artifact-boundary.yml`, which executes `scripts/run_contract_preflight.py` and then validates `outputs/contract_preflight/contract_preflight_result_artifact.json` as the trust authority for pytest execution and selection integrity.

## 2. Files added
- `docs/review-actions/PLAN-TSI-02-2026-04-14.md`
- `docs/reviews/TSI-02_real_pr_seam_enforcement_review.md`

## 3. Files modified
- `.github/workflows/artifact-boundary.yml`
- `.github/workflows/pr-autofix-contract-preflight.yml`
- `scripts/run_contract_preflight.py`
- `spectrum_systems/modules/runtime/preflight_failure_normalizer.py`
- `spectrum_systems/modules/runtime/github_pr_autofix_contract_preflight.py`
- `tests/test_artifact_boundary_workflow_pytest_enforcement.py`
- `tests/test_contract_preflight.py`
- `tests/test_github_pr_autofix_contract_preflight.py`

## 4. What was previously unwired
`artifact-boundary.yml` returned early when `run_contract_preflight.py` exited 0, bypassing workflow-level artifact trust checks on the actual happy path. This allowed the real PR seam to skip execution/selection artifact validation despite having report/schema coverage.

## 5. What is now enforced
- Workflow no longer bypasses artifact validation on `preflight_exit==0`; artifact checks run on the real PR path.
- PR allow/warn now fail-closes if either execution artifact or selection-integrity artifact is missing/invalid/blocked.
- Preflight now emits explicit invariant `PR_PYTEST_SELECTION_INTEGRITY_REQUIRED` alongside fail-closed selection reason codes.
- Autofix classification handles `PR_PYTEST_SELECTION_INTEGRITY_REQUIRED` deterministically as a selection-integrity failure class.

## 6. Tests added/updated
- Workflow-adjacent seam tests assert no early bypass and assert selection-integrity guard clauses in both workflows.
- Preflight regression test asserts explicit `PR_PYTEST_SELECTION_INTEGRITY_REQUIRED` invariant presence.
- Autofix classification regression test covers `PR_PYTEST_SELECTION_INTEGRITY_REQUIRED` mapping.

## 7. Validation commands run
1. `python scripts/run_contract_preflight.py --help`
2. `python -m pytest -q tests/test_contract_preflight.py`
3. `python -m pytest -q tests/test_github_pr_autofix_contract_preflight.py`
4. `python -m pytest -q tests/test_pytest_selection_integrity.py`
5. `python -m pytest -q tests/test_artifact_boundary_workflow_pytest_enforcement.py`
6. `python scripts/run_contract_enforcement.py`

## 8. Exact results
- help command passed.
- `tests/test_contract_preflight.py` passed.
- `tests/test_github_pr_autofix_contract_preflight.py` passed.
- `tests/test_pytest_selection_integrity.py` passed.
- `tests/test_artifact_boundary_workflow_pytest_enforcement.py` passed.
- contract enforcement passed with zero failures.

## 9. Remaining risks
- Workflow assertions are string-based (workflow-adjacent); they prove seam wiring but not execution semantics of GitHub runner itself.
- Governance policy drift still requires same-change updates when new governed surfaces are added.
