# Parallel PQX Post-Run Validation (2-Slice)

## Purpose
Define the required, fail-closed post-run validation artifact for completed **2-slice parallel PQX** runs.

This artifact is governance documentation only. It does **not** change runtime behavior, tests, certification logic, or CLI/CI behavior.

## Required artifact
For each completed 2-slice parallel PQX run, operators must produce a record using:
- `docs/review-actions/parallel_pqx_postrun_template.md`

A run is **not valid** unless all required fields are completed with explicit evidence.

## Required fields (must be explicit)
The post-run record must explicitly include all of the following:

1. Slice A identifier
2. Slice B identifier
3. Files touched by Slice A
4. Files touched by Slice B
5. Merge order (fixed enum: `A→B` or `B→A`)
6. BEFORE behavior for Slice A
7. BEFORE behavior for Slice B
8. AFTER behavior for Slice B
9. Explicit BEFORE vs AFTER comparison (for B)
10. File overlap result (`none` / `overlap`)
11. Semantic overlap result (`none` / `overlap`)
12. Shared assumption result (`none` / `present`)
13. Attribution clarity (`clear` / `unclear`)
14. Promotion/certification path status (`unchanged` / `requires-review` / `blocked`)
15. Final outcome (`pass` / `fail`)

## Fail-closed rule (mandatory)
Validation is **fail-closed**. The final outcome must be `fail` if any of the following conditions occur:

- Any required evidence is missing.
- Attribution between slices is unclear.
- BEFORE vs AFTER behavior comparison is ambiguous.
- Any required field is left as unknown, tentative, or “looks okay”.

No soft conclusion is allowed.

## Decision standard
A run may be marked `pass` only when all of the below are true:

- All required fields are complete and evidence-backed.
- Attribution for observed behavior is clear to one slice or to a documented shared mechanism.
- BEFORE vs AFTER comparison for Slice B is explicit and unambiguous.
- Overlap and shared-assumption checks are completed and dispositioned.
- Promotion/certification path status is explicitly recorded.

If any condition is not met, the run outcome is `fail`.
