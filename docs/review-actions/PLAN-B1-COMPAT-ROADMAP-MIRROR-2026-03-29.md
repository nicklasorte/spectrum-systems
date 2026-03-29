# Plan — B1 Compatibility Roadmap Mirror Repair — 2026-03-29

## Prompt type
PLAN

## Roadmap item
B1 fix (RM-01 + RM-02 compatibility repair)

## Objective
Restore `docs/roadmap/system_roadmap.md` as a parseable operational compatibility mirror for existing PQX/tests while preserving `docs/roadmaps/system_roadmap.md` as active editorial authority.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-B1-COMPAT-ROADMAP-MIRROR-2026-03-29.md | CREATE | Required multi-file plan artifact for narrow B1 compatibility fix |
| docs/roadmap/system_roadmap.md | MODIFY | Reintroduce parseable roadmap table, compatibility note, and roadmap step contract references |
| docs/roadmaps/system_roadmap.md | MODIFY | Add explicit dual-surface transition rule (active authority + operational mirror) |
| docs/roadmaps/roadmap_authority.md | MODIFY | Document compatibility rule and migration condition |
| tests/test_roadmap_authority.py | MODIFY | Minimal dual-surface transition-model assertion updates if needed |
| docs/review-actions/B1_COMPATIBILITY_REPAIR_SUMMARY_2026-03-29.md | CREATE | Explain failure cause, governing compatibility rule, and future full-migration slice |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_pqx_backbone.py`
2. `pytest tests/test_roadmap_step_contract.py`
3. `pytest tests/test_roadmap_authority.py`
4. `pytest tests/test_roadmap_tracker.py`
5. `pytest tests/test_contracts.py`
6. `pytest tests/test_module_architecture.py`
7. `pytest`
8. `PLAN_FILES='docs/review-actions/PLAN-B1-COMPAT-ROADMAP-MIRROR-2026-03-29.md docs/roadmap/system_roadmap.md docs/roadmaps/system_roadmap.md docs/roadmaps/roadmap_authority.md tests/test_roadmap_authority.py docs/review-actions/B1_COMPATIBILITY_REPAIR_SUMMARY_2026-03-29.md' .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign PQX architecture.
- Do not change runtime behavior outside roadmap compatibility restoration.
- Do not add or change contracts/schemas.
- Do not broaden roadmap rewrite beyond compatibility and authority transition wording.

## Dependencies
- Existing PQX parser/tests depend on `docs/roadmap/system_roadmap.md` table shape and row IDs.
