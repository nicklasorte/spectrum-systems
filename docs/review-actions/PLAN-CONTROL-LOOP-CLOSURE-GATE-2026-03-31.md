# Plan — CONTROL-LOOP-CLOSURE-GATE — 2026-03-31

## Prompt type
PLAN

## Roadmap item
Roadmap authority reconciliation + Control Loop Closure Gate insertion (March 31, 2026 revision)

## Objective
Save the March 31, 2026 roadmap as repo-governed authority, preserve compatibility mirror behavior, and add a mandatory pre-expansion Control Loop Closure Gate that blocks broader execution expansion until failure learning becomes binding.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/roadmaps/system_roadmap.md | MODIFY | Install March 31 authority update and insert mandatory Control Loop Closure Gate + ordered execution structure. |
| docs/roadmap/system_roadmap.md | MODIFY | Keep legacy machine-parseable compatibility mirror aligned to authority changes including gate requirement. |
| docs/roadmaps/roadmap_authority.md | MODIFY | Preserve authority/mirror bridge and add pre-expansion gate rule. |
| docs/roadmap/roadmap_step_contract.md | MODIFY | Reconcile authority wording so contract references active authority plus compatibility execution surface. |
| docs/architecture/strategy_control_document.md | CREATE | Add stable governing strategy/control doc for roadmap generation + drift prevention. |
| docs/roadmaps/2026-03-31-roadmap-transition-note.md | CREATE | Record supersession rationale and transition constraints for March 31 revision. |
| docs/review-actions/PLAN-CONTROL-LOOP-CLOSURE-GATE-2026-03-31.md | CREATE | Required PLAN artifact for this multi-file governance change. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_roadmap_authority.py tests/test_roadmap_step_contract.py tests/test_roadmap_tracker.py`
2. `python scripts/check_roadmap_authority.py`
3. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not modify runtime implementation modules.
- Do not change JSON schemas or standards manifest pins.
- Do not remove compatibility mirror behavior.
- Do not claim MVP closed-loop control is already complete.

## Dependencies
- Existing authority bridge in `docs/roadmaps/roadmap_authority.md` remains in force.
- Existing mirror parse shape in `docs/roadmap/system_roadmap.md` remains parseable for legacy PQX consumers.
