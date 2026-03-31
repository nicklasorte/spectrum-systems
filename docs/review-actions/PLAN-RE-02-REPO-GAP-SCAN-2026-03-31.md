# Plan — RE-02 Repo Gap Scan — 2026-03-31

## Prompt type
PLAN

## Roadmap item
RE-02 — Repo Gap Scan

## Objective
Produce a grounded, source-vs-repo obligation coverage scan for seeded AI durability obligations in the repo-native reporting surface.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-RE-02-REPO-GAP-SCAN-2026-03-31.md | CREATE | Required plan-first artifact for RE-02 scan execution. |
| PLANS.md | MODIFY | Register this RE-02 plan in the active plans table. |
| docs/roadmaps/execution_state_inventory.md | MODIFY | Add repo-native RE-02 source-obligation gap scan report with grounded classifications. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_source_indexes_build.py`
2. `pytest tests/test_source_structured_files_validate.py`
3. `pytest tests/test_source_design_extraction_schema.py`
4. `pytest tests/test_roadmap_tracker.py`
5. `PLAN_FILES="docs/review-actions/PLAN-RE-02-REPO-GAP-SCAN-2026-03-31.md PLANS.md docs/roadmaps/execution_state_inventory.md" .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not generate or replace system roadmap content.
- Do not alter source index builder logic.
- Do not make runtime/module behavior changes.
- Do not add speculative component-source mappings without grounded repo evidence.

## Dependencies
- docs/source_indexes/obligation_index.json must remain authoritative for obligation IDs and descriptions.
