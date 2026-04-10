# PLAN-BATCH-AUT-REG-03-2026-04-10

## Prompt type
PLAN

## Scope
Upgrade `contracts/roadmap/slice_registry.json` into a stricter PQX execution contract by replacing generic commands/notes with slice-specific execution guidance, and enforce fail-closed validation/test coverage for generic or mismatched metadata.

## Files
- MODIFY `contracts/roadmap/slice_registry.json`
- MODIFY `spectrum_systems/modules/runtime/roadmap_slice_registry.py`
- MODIFY `tests/test_roadmap_slice_registry.py`
- ADD `tests/test_slice_registry_execution_contract.py`
- ADD `docs/reviews/RVW-BATCH-AUT-REG-03.md`
- ADD `docs/reviews/BATCH-AUT-REG-03-DELIVERY-REPORT.md`

## Steps
1. Inventory current slice families and map each slice to at least one deterministic, slice-specific execution command that exercises real repo logic.
2. Replace generic `implementation_notes` with actionable, fail-closed behavior statements per slice.
3. Extend runtime validation to fail on generic-only commands, generic notes, command collisions across slices, and execution_type/command mismatches.
4. Add targeted tests for the new fail-closed checks plus a positive valid-slice case.
5. Run focused tests and full `pytest`; then write review + delivery report artifacts.

## Validation commands
1. `pytest tests/test_roadmap_slice_registry.py tests/test_slice_registry_execution_contract.py -q`
2. `pytest`
