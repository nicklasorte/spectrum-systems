# PYX-02 — Visible pytest PR check review

## 1. Intent
Establish pytest as a first-class, explicit, stable pull-request check on the GitHub merge surface while preserving artifact-first, fail-closed enforcement through the existing governed contract preflight path.

## 2. Root cause of missing PR-visible pytest signal
The workflow had a dedicated `contract-preflight` job that performed authoritative pytest execution and selection-integrity trust checks, but the PR UI signal was operator-ambiguous because:
- the authoritative job name was not pytest-explicit, and
- a separate non-authoritative redundancy job (`run-pytest`) existed with a pytest-facing label, which diluted operator clarity about which check was trust-authoritative.

## 3. Files added
- `docs/reviews/PYX-02_visible_pytest_pr_check_review.md`

## 4. Files modified
- `.github/workflows/artifact-boundary.yml`
- `tests/test_artifact_boundary_workflow_pytest_enforcement.py`

## 5. Exact workflow/job names before and after
Workflow name (unchanged):
- `artifact-boundary`

Before:
- `contract-preflight` (authoritative preflight/pytest trust enforcement)
- `run-pytest` (non-authoritative redundancy)

After:
- `pytest-pr` with explicit display name `PR / pytest` (authoritative preflight/pytest trust enforcement)
- `run-pytest` (non-authoritative redundancy), now explicitly dependent on `pytest-pr`

## 6. How single-source-of-truth trust enforcement was preserved
- No trust logic was duplicated into a weaker standalone path.
- The same governed preflight execution path (`scripts/run_contract_preflight.py`) remains the authority.
- The explicit pytest-visible PR check is a rename/relabel of the authoritative preflight job surface, not an independent lightweight pytest runner.
- Existing fail-closed assertions remain intact in that job for:
  - missing `pytest_execution_record_ref`
  - missing/blocked `pytest_selection_integrity_result_ref`
  - non-canonical artifact refs
  - provenance/linkage mismatches
  - PR `WARN` non-pass semantics

## 7. Which status check should be marked required
Configure the required status check as:
- **`PR / pytest`**

This is the explicit, stable, operator-visible check name for governed pytest trust enforcement on pull requests.

## 8. Tests added/updated
Updated:
- `tests/test_artifact_boundary_workflow_pytest_enforcement.py`
  - added assertions that the workflow defines explicit job id `pytest-pr`
  - added assertion for stable visible job name `PR / pytest`
  - added assertion that downstream redundancy job depends on `pytest-pr` and no longer references `contract-preflight`

## 9. Validation commands run
1. `python -m pytest -q tests/test_artifact_boundary_workflow_pytest_enforcement.py`
2. `python -m pytest -q tests/test_contract_preflight.py`
3. `python -m pytest -q tests/test_pytest_selection_integrity.py`
4. `python scripts/run_contract_enforcement.py`

## 10. Exact results
- All four required validation commands passed in the local execution environment.

## 11. Remaining risks
- Branch protection in GitHub must be updated to require `PR / pytest`; until that setting is changed, operator visibility is improved but protection policy may still target an old check name.
- If GitHub job display naming conventions change, required-check configuration should continue targeting the explicit job name surfaced by workflow runs.
