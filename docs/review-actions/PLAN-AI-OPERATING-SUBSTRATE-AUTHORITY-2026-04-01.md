# Plan — AI Operating Substrate Authority Wiring — 2026-04-01

## Prompt type
PLAN

## Roadmap item
Governance slice — AI operating substrate authority adoption

## Objective
Make the AI operating substrate design document a required roadmap authority, record current substrate gaps, and publish the first dependency-valid MVP build wave.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/architecture/ai_operating_substrate_and_artifact_intelligence.md | CREATE | Land canonical design authority for substrate + artifact intelligence. |
| docs/architecture/strategy-control.md | MODIFY | Add required authority input, hard sequencing rules, drift signals, and expansion block condition tied to substrate must-add gaps. |
| docs/architecture/strategy_guided_roadmap_prompt.md | MODIFY | Require roadmap generator to inspect repo against strategy/foundation/substrate and sequence accordingly. |
| docs/architecture/ai_operating_substrate_gap_analysis.md | CREATE | Compare repository reality vs substrate design requirements and identify hard gates. |
| docs/roadmaps/ai_operating_substrate_mvp_build_plan.md | CREATE | Define first 8–12 dependency-valid MVP build steps only. |

## Contracts touched
None.

## Tests that must pass after execution
1. `python scripts/check_roadmap_authority.py`
2. `python scripts/run_roadmap_eligibility.py`

## Scope exclusions
- Do not implement substrate runtime features.
- Do not expand autonomy breadth.
- Do not add broad dashboard or tournament systems.
- Do not modify contracts/schemas in this slice.

## Dependencies
- Existing strategy and foundation architecture documents must remain authoritative.
