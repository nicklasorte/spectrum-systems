# BATCH-GOV-FIX-03 Delivery Report

## 1. Intent
Repair `run_prompt_with_governance` execution for prompt files outside repository root while preserving fail-closed governance blocking semantics and aligning tests with canonical blocking output.

## 2. Root Cause
The wrapper invokes `check_governance_compliance.py --file <prompt_path>`. In GOV-FIX-02, `evaluate_prompt_file()` used `file_path.resolve().relative_to(REPO_ROOT)` unguarded, which raises `ValueError` for external temp paths (e.g., pytest `tmp_path`). That crash caused valid external prompts to fail and changed the observed failure stream for invalid cases.

## 3. Files Updated
- `docs/review-actions/PLAN-BATCH-GOV-FIX-03-2026-04-07.md` (new PLAN artifact)
- `scripts/check_governance_compliance.py`
- `scripts/run_prompt_with_governance.py`
- `tests/test_run_prompt_with_governance.py`
- `docs/execution_reports/BATCH-GOV-FIX-03_delivery_report.md`
- `docs/roadmaps/NEXT_SLICE.md`
- `docs/roadmaps/SLICE_HISTORY.md`

## 4. Repair Applied
- Added safe path normalization in checker (`_path_for_surface_classification`) that returns repo-relative path when possible and `None` otherwise.
- Updated `evaluate_prompt_file()` to:
  - read prompt text first,
  - use repo-surface classification only for in-repo files,
  - fall back to fail-closed raw-text governance validation for external files.
- Updated wrapper with safe display-path handling (`_display_prompt_path`) using repo-relative path when possible, absolute path otherwise.
- Preserved canonical blocking message: `BLOCKED: governance preflight failed; prompt execution stopped.`
- Updated wrapper tests to assert pass/fail behavior on external temp-path prompts and canonical blocking output.

## 5. Governance Guarantees Preserved
- Fail-closed semantics are preserved for invalid prompts (non-zero + explicit BLOCKED line).
- No enforcement weakening was introduced.
- External prompt files are now validated rather than crashing or bypassing governance checks.

## 6. Validation Performed
1. `python -m pytest tests/test_run_prompt_with_governance.py tests/test_governance_prompt_enforcement.py tests/test_governed_prompt_surface_sync.py`
2. `python -m pytest`

Result:
- Narrow set: PASS (12 passed).
- Full suite: PASS (`5738 passed, 1 skipped`).

Original failing tests repaired:
- `test_run_prompt_with_governance_passes_for_valid_prompt`: repaired.
- `test_run_prompt_with_governance_blocks_invalid_prompt`: repaired.

## 7. Remaining Gaps
- `run_prompt_with_governance.py` still prints checker stdout/stderr directly; if future checker output shape changes, wrapper tests may need wording updates.

## 8. Next Recommended Slice
Add a small dedicated checker unit test for external-path file validation directly in `tests/test_governance_prompt_enforcement.py` to lock behavior at checker level in addition to wrapper-level coverage.
