# Plan — FOUNDATION-AUTHORITY-WIRING — 2026-04-01

## Prompt type
PLAN

## Roadmap item
ROADMAP-GOVERNANCE-FOUNDATION-AUTHORITY-WIRING

## Objective
Make the foundation architecture document mandatory in strategy and roadmap-generation authority wiring, with fail-closed enforcement for foundation-first sequencing.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-FOUNDATION-AUTHORITY-WIRING-2026-04-01.md | CREATE | Record required PLAN before multi-file governance wiring update. |
| PLANS.md | MODIFY | Register this active plan in the repository plan index table. |
| docs/architecture/foundation_pqx_eval_control.md | CREATE | Add canonical foundation architecture authority document required by roadmap generation. |
| docs/architecture/strategy-control.md | MODIFY | Add foundation authority ordering, hard gate rules, drift signals, and foundation-first build priorities. |
| docs/architecture/strategy_guided_roadmap_prompt.md | MODIFY | Update reusable roadmap generator prompt to require foundation pre-checks, classification, and anti-drift sequencing. |
| docs/roadmaps/roadmap_authority.md | MODIFY | Normalize authority order and cross-reference required strategy + foundation governance for roadmap generation. |
| docs/roadmaps/roadmap_generator_authority.md | CREATE | Add explicit roadmap generator authority note with mandatory strategy + foundation usage and expansion block rule. |
| scripts/check_strategy_compliance.py | MODIFY | Enforce fail-closed compliance checks for required foundation authority usage/order in roadmap generation prompt(s). |

## Contracts touched
None.

## Tests that must pass after execution
1. `python scripts/check_strategy_compliance.py`
2. `python scripts/check_roadmap_authority.py`

## Scope exclusions
- Do not modify runtime implementation logic.
- Do not modify schemas or contracts.
- Do not change eval/control runtime behavior.
- Do not redesign roadmap structure beyond governance authority wiring.

## Dependencies
- docs/architecture/strategy-control.md remains the top governing document.
