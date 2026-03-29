# Plan — PQX Execution Contract Standard — 2026-03-28

## Prompt type
PLAN

## Roadmap item
PQX governance step — roadmap step execution contract standard

## Objective
Define a repo-native written standard and reusable slice template so roadmap rows can be upgraded into deterministic PQX-executable contracts.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/roadmap/roadmap_step_contract.md | CREATE | Publish the required PQX roadmap step contract standard. |
| docs/roadmap/slices/_TEMPLATE.md | CREATE | Provide reusable execution slice template aligned to the contract. |
| docs/roadmap/system_roadmap.md | MODIFY | Add a surgical note referencing the new roadmap step contract standard and slice location. |
| tests/test_roadmap_step_contract.py | CREATE | Add narrow validation that required contract/template docs exist and roadmap references them. |

## Contracts touched
None.

## Tests that must pass after execution
List the specific test commands to run to validate this plan.

1. `pytest tests/test_roadmap_step_contract.py`

## Scope exclusions
Explicitly list things that are NOT in scope for this plan.
This prevents accidental expansion.

- Do not rewrite roadmap rows.
- Do not add or modify JSON schemas in `contracts/schemas/`.
- Do not change contracts/standards-manifest.json.
- Do not refactor queue/runtime/control modules.

## Dependencies
List any prior roadmap items that must be complete before this plan can execute.

- None
