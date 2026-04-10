# Plan — BATCH-AUT-REG-04 — 2026-04-10

## Prompt type
BUILD

## Roadmap item
BATCH-AUT-REG-04

## Objective
Replace self-referential slice registry execution commands with real behavior-first commands, harden fail-closed validators, and add targeted tests/review artifacts for deterministic autonomy progression.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| contracts/roadmap/slice_registry.json | MODIFY | Replace fake commands with behavior-first command pairs and concrete implementation notes across all slice families. |
| spectrum_systems/modules/runtime/roadmap_slice_registry.py | MODIFY | Add fail-closed validation for fake/self-referential commands, family-level duplicate command sets, and stronger behavior-first alignment checks. |
| tests/test_slice_registry_execution_contract.py | MODIFY | Add/adjust tests for fake command rejection, first-command behavior gating, duplicate family command rejection, boilerplate notes rejection, and valid behavior-first pass path. |
| docs/reviews/RVW-BATCH-AUT-REG-04.md | CREATE | Required review artifact answering autonomy/ownership questions and verdict. |
| docs/reviews/BATCH-AUT-REG-04-DELIVERY-REPORT.md | CREATE | Required delivery report summarizing upgrades, validator/test gates, and remaining weak areas. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_slice_registry_execution_contract.py -q`
2. `pytest tests/test_roadmap_slice_registry.py -q`

## Scope exclusions
- Do not modify `contracts/roadmap/roadmap_structure.json`.
- Do not add new systems/modules beyond existing runtime and tests.
- Do not weaken existing validator constraints.

## Dependencies
- Existing slice registry + roadmap structure artifacts remain canonical inputs.
