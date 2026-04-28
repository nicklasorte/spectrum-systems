# PLAN — TST-01 authority-shape remediation (Prompt type: REVIEW)

## Scope
Remediate PR #1279 authority-shape preflight failures and strengthen earlier detection in the RFX super-check path without broadening taxonomy.

## Steps
1. Reproduce and enumerate all authority-shape violations from the governed preflight artifact.
2. Apply minimal vocabulary remediation in `docs/reviews/TST-01_ci_test_inventory.md` using suggested replacements where semantics match.
3. Strengthen `scripts/run_rfx_super_check.py` to run authority-shape preflight in suggest-only mode against changed files and emit actionable details (file/line/symbol/replacements).
4. Add focused regression tests in `tests/test_run_rfx_super_check.py` covering failure detection for ambiguous terms and pass behavior for safe replacements.
5. Re-run authority-shape preflight and targeted tests; then run full `pytest` if affordable.
6. Commit changes and publish PR update.
