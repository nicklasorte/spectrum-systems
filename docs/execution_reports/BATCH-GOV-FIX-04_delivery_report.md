# BATCH-GOV-FIX-04 Delivery Report

## 1. Intent
Add direct checker-level regression tests for `evaluate_prompt_file()` using prompt files outside repository root so external-path governance behavior is locked independently of wrapper execution.

## 2. Files Updated
- `docs/review-actions/PLAN-BATCH-GOV-FIX-04-2026-04-07.md` (PLAN artifact)
- `tests/test_governance_prompt_enforcement.py`
- `docs/execution_reports/BATCH-GOV-FIX-04_delivery_report.md`
- `docs/roadmaps/NEXT_SLICE.md`
- `docs/roadmaps/SLICE_HISTORY.md`

## 3. Checker-Level Regression Coverage Added
Added two direct checker-layer tests in `tests/test_governance_prompt_enforcement.py` that call `evaluate_prompt_file()` with `tmp_path` files (external to repo root):

1. External valid prompt content passes with deterministic checker metadata:
   - `passed=True`
   - `governed=True`
   - `surface_id="raw_text_default"`
   - `missing_items=[]`

2. External invalid prompt content fails fail-closed with deterministic missing-reference diagnostics:
   - `passed=False`
   - `governed=True`
   - `surface_id="raw_text_default"`
   - includes `missing required reference: docs/governance/source_inputs_manifest.json`

This locks external-path behavior at checker level and removes dependency on wrapper path handling for this regression class.

## 4. Governance Guarantees Preserved
- Fail-closed behavior is preserved for invalid external prompts.
- No checker enforcement policy was weakened.
- No logic was moved from checker to wrapper.
- No pytest-only branch logic was introduced in production scripts.

## 5. Validation Performed
Narrow validation:
1. `pytest tests/test_governance_prompt_enforcement.py tests/test_run_prompt_with_governance.py tests/test_governed_prompt_surface_sync.py`

Full validation:
2. `pytest`

Results:
- Narrow suite: PASS (`14 passed`).
- Full suite: PASS (`5740 passed, 1 skipped`).

## 6. Remaining Gaps
- Checker-level external-path behavior is now directly covered, but diagnostics contract is still string-based; if diagnostic message schema is formalized later, tests should migrate from string matching to structured fields.

## 7. Next Recommended Slice
Harden checker diagnostics contract with a small structured diagnostic payload (stable codes + paths) while preserving current CLI output, then update tests to assert code-level diagnostics instead of message text fragments.
