# Plan — RE-04 Candidate Roadmap Validation — 2026-03-31

## Prompt type
PLAN

## Roadmap item
RE-04 — Candidate roadmap validation (REVIEW/VALIDATE slice)

## Objective
Validate `docs/roadmaps/re-03-candidate-roadmap-source-grounded.md` against source obligations, authority surfaces, compatibility constraints, and required validation checks, then publish a dated validation report with a fail-closed verdict.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-RE-04-CANDIDATE-ROADMAP-VALIDATION-2026-03-31.md | CREATE | Required plan-first artifact before RE-04 validation updates |
| docs/reviews/2026-03-31-re-04-candidate-roadmap-validation.md | CREATE | Required RE-04 validation report with findings and merge-readiness verdict |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_source_indexes_build.py`
2. `pytest tests/test_source_structured_files_validate.py`
3. `pytest tests/test_source_design_extraction_schema.py`
4. `pytest tests/test_roadmap_authority.py tests/test_roadmap_step_contract.py tests/test_roadmap_tracker.py`
5. `python scripts/check_roadmap_authority.py`
6. `PLAN_FILES="docs/review-actions/PLAN-RE-04-CANDIDATE-ROADMAP-VALIDATION-2026-03-31.md docs/reviews/2026-03-31-re-04-candidate-roadmap-validation.md" .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not modify `docs/roadmaps/system_roadmap.md`.
- Do not modify `docs/roadmap/system_roadmap.md`.
- Do not redesign roadmap sequencing or create a replacement roadmap.
- Do not weaken tests/checkers.

## Dependencies
- `docs/roadmaps/re-03-candidate-roadmap-source-grounded.md` must exist on the current branch as the candidate artifact under review.
