# Plan — BATCH-PFG-AFX-RGM-01 — 2026-04-10

## Prompt type
BUILD

## Roadmap item
BATCH-PFG-AFX-RGM-01

## Objective
Implement mandatory preflight gating, canonical validation entrypoint enforcement, artifact spine enforcement, and governance radar integration with fail-closed blocking on overdue governance risk.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-PFG-AFX-RGM-01-2026-04-10.md | CREATE | Required multi-file execution plan before BUILD scope touching >2 files. |
| scripts/check_review_registry.py | MODIFY | Add governance radar scan + signal artifact emission/classification for PRG consumption. |
| scripts/run_review_artifact_validation.py | MODIFY | Consume canonical governance radar output and expose it in validation result artifacts. |
| spectrum_systems/modules/runtime/github_pr_autofix_review_artifact_validation.py | MODIFY | Integrate governance signal into preflight and fail-closed behavior for overdue risk. |
| tests/test_github_pr_autofix_review_artifact_validation.py | MODIFY | Add/align required tests for preflight, validation path consistency, artifact spine, and governance integration. |
| docs/reviews/pfg_afx_rgm_redteam.md | CREATE | Mandatory targeted red-team review report for this batch seam. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_github_pr_autofix_review_artifact_validation.py`
2. `pytest tests/test_contracts.py`

## Scope exclusions
- Do not introduce new runtime systems or ownership models.
- Do not change AEX/PQX/SEL/TLC/FRE/PRG authority boundaries beyond explicit artifact wiring.
- Do not modify unrelated workflows or broad refactor existing governance scripts.

## Dependencies
- Canonical ownership and boundaries from `docs/architecture/system_registry.md`.
- Runtime identity and fail-closed principles from `README.md`.
