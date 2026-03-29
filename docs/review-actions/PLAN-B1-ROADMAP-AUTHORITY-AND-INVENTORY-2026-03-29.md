# Plan — B1 Roadmap Authority and Inventory — 2026-03-29

## Prompt type
PLAN

## Roadmap item
RM-01 + RM-02 (Bundle B1)

## Objective
Establish a single active roadmap authority and a repo-grounded execution-state inventory for PQX/governed multi-slice execution without introducing new runtime behavior.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-B1-ROADMAP-AUTHORITY-AND-INVENTORY-2026-03-29.md | CREATE | Required B1 plan artifact before multi-file documentation changes |
| docs/roadmaps/system_roadmap.md | MODIFY | Promote as active roadmap authority with required sections and grounded roadmap table |
| docs/roadmaps/execution_state_inventory.md | CREATE | Add RM-02 current-state implementation inventory |
| docs/roadmaps/roadmap_authority.md | CREATE | Add operational authority note (active/subordinate/reference treatment) |
| docs/review-actions/B1_EXECUTION_SUMMARY_2026-03-29.md | CREATE | Add concise execution summary with designation and gap findings |
| docs/roadmap/system_roadmap.md | MODIFY | Mark as subordinate reference and redirect authority to active roadmap |
| docs/roadmap/README.md | MODIFY | Align roadmap authority index to active roadmap location |
| AGENTS.md | MODIFY | Reconcile repository-level roadmap execution rule with active authority |
| CODEX.md | MODIFY | Reconcile Codex roadmap execution rule with active authority |
| tests/test_roadmap_authority.py | MODIFY | Keep authority validation aligned to single active roadmap designation |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_roadmap_authority.py`
2. `pytest tests/test_roadmap_tracker.py`
3. `pytest tests/test_contracts.py`
4. `pytest tests/test_module_architecture.py`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not implement runtime/module logic changes.
- Do not add or change JSON schemas in `contracts/schemas/`.
- Do not redesign roadmap phases beyond B1 authority consolidation and inventory.
- Do not delete historical roadmap documentation; only relabel as subordinate/reference where needed.

## Dependencies
- Existing roadmap and PQX documentation seams remain available for consolidation.
- Existing review/certification/replay/observability docs and tests provide current-state evidence.
