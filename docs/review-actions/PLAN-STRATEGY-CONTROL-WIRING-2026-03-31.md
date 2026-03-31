# Plan — STRATEGY-CONTROL-WIRING — 2026-03-31

## Prompt type
PLAN

## Roadmap item
STRATEGY-CONTROL-WIRING

## Objective
Promote the Strategy Control Document into a single canonical repo-native authority and hard-wire roadmap-generation inputs to consume it first.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-STRATEGY-CONTROL-WIRING-2026-03-31.md | CREATE | Required PLAN artifact before multi-file governance wiring |
| docs/architecture/strategy-control.md | CREATE | Canonical governing strategy authority surface |
| docs/architecture/strategy_control_document.md | DELETE | Remove duplicate competing strategy document path |
| docs/architecture/strategy_guided_roadmap_prompt.md | MODIFY | Enforce strict roadmap input precedence and invariant validation |
| docs/roadmaps/roadmap_authority.md | MODIFY | Bind roadmap authority policy to canonical strategy document |
| docs/roadmaps/system_roadmap.md | MODIFY | Update strategy-control references to canonical path |
| docs/roadmaps/execution_state_inventory.md | MODIFY | Update source input and strategy-control references |
| docs/roadmaps/re-03-candidate-roadmap-source-grounded.md | MODIFY | Update authoritative input ordering and canonical strategy path |
| docs/roadmap/README.md | MODIFY | Add primary governing Strategy Control Document reference |
| spectrum-data-lake/raw/strategic_sources/project_design/README.md | CREATE | Link supporting source folder to canonical governing strategy authority |

## Contracts touched
None.

## Tests that must pass after execution
1. `python scripts/check_roadmap_authority.py`
2. `.codex/skills/verify-changed-scope/run.sh docs/review-actions/PLAN-STRATEGY-CONTROL-WIRING-2026-03-31.md`

## Scope exclusions
- Do not change strategy document meaning.
- Do not redesign roadmap phases, step IDs, or execution semantics.
- Do not modify contracts or runtime module code.

## Dependencies
- None.
