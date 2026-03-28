# Parallel PQX Slice Classification Template

Use one block per slice. All fields are required.

## Slice Classification Record

- **Slice ID:** `PQX-...`
- **Title:** `<short title>`
- **Primary Surface (`primary_surface`):** `docs_review_governance | isolated_runtime | isolated_test | shared_runtime | shared_test | schema_contract | control_loop_policy | certification_gate | registry_manifest`
- **Sharedness Risk (`sharedness_risk`):** `none | low | high`
- **Control Sensitivity (`control_sensitivity`):** `none | medium | critical`
- **Files Likely Touched:**
  - `path/to/file`
  - `path/to/file`
- **Parallel Eligibility (`parallel_eligibility`):** `parallel_safe | conditional | not_parallel_safe`
- **Rationale:** `<1-3 sentences using explicit policy terms only>`

## Fail-Closed Check

Mark **PASS** only when every item below is true.

- [ ] Classification is complete for all required dimensions.
- [ ] No uncertainty remains in selected class.
- [ ] No mixed interpretation includes a `not_parallel_safe` class.
- [ ] Expected touched files are known.
- [ ] If any box is unchecked, set eligibility to `not_parallel_safe`.
