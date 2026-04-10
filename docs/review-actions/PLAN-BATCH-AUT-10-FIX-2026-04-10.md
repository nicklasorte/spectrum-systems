# Plan — BATCH-AUT-10-FIX — 2026-04-10

## Prompt type
PLAN

## Roadmap item
BATCH-AUT-10-FIX

## Objective
Repair AUT-10 governed control-decision fixture contract mismatch without weakening validation, then resume governed execution from AUT-10 to determine true next blocker/completion state.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-AUT-10-FIX-2026-04-10.md | CREATE | Required written plan before multi-file changes. |
| tests/fixtures/roadmaps/aut_reg_05a/review_control_signal.json | MODIFY | Canonical fixture contract repair for AUT-10 control decision shape. |
| contracts/roadmap/slice_registry.json | MODIFY (only if required) | Surgical command-shape correction if AUT-10 command passes wrong decision object shape. |
| docs/reviews/RVW-BATCH-AUT-10-FIX.md | CREATE | Required governed review artifact with verdict and batch outcome. |
| docs/reviews/BATCH-AUT-10-FIX-DELIVERY-REPORT.md | CREATE | Delivery report with changed fields, validation, and resumed execution outcomes. |

## Contracts touched
None.

## Tests that must pass after execution
1. `python -c "import json; from spectrum_systems.modules.runtime.review_roadmap_generator import build_review_roadmap; snapshot=json.load(open('tests/fixtures/roadmaps/aut_reg_05a/repo_review_snapshot.json')); decision=json.load(open('tests/fixtures/roadmaps/aut_reg_05a/review_control_signal.json')); program={'program_id':'PRG-AUT-10','allowed_targets':['modules/runtime'],'priority_rules':[],'blocked_patterns':[],'updated_at':'2026-04-10T00:00:00Z'}; build_review_roadmap(snapshot=snapshot, control_decision=decision, program_artifact=program)"`
2. `pytest tests/test_review_roadmap_generator.py -q`
3. Governed resume execution from AUT-10 using `contracts/roadmap/slice_registry.json` + `contracts/roadmap/roadmap_structure.json`.

## Scope exclusions
- Do not modify runtime logic in `spectrum_systems/modules/runtime/review_roadmap_generator.py`.
- Do not add prompt-driven execution behavior.
- Do not bypass fail-closed errors.
- Do not broaden changes into unrelated slices.

## Dependencies
- AUT-09 and preceding BATCH-AUT slices are assumed complete from prior artifact-driven execution state.
