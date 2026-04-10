# Plan — GRC-INTEGRATION-01 — 2026-04-10

## Prompt type
PLAN

## Roadmap item
GRC-INTEGRATION-01 (GOVERNED_REPAIR_LOOP_CLOSURE)

## Objective
Implement and validate an end-to-end governed repair loop that uses real AUT-05/AUT-07/AUT-10 failure cases to drive failure packetization, bounded repair decisioning, gating, execution, review, and resume without prompt-dependent logic.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-GRC-INTEGRATION-01-2026-04-10.md | CREATE | Required plan-first declaration for multi-file governed integration update. |
| spectrum_systems/modules/runtime/governed_repair_loop_execution.py | CREATE | Add deterministic artifact-driven orchestration for failure→repair→resume loop. |
| tests/test_governed_repair_loop_execution.py | CREATE | Add end-to-end and fail-closed path coverage for AUT-05/AUT-07/AUT-10 real failure cases. |
| docs/reviews/RVW-GRC-INTEGRATION-01.md | CREATE | Mandatory governed system review with loop closure and integrity verdict. |
| docs/reviews/GRC-INTEGRATION-01-DELIVERY-REPORT.md | CREATE | Mandatory delivery report summarizing implementation and test outcomes. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_governed_repair_loop_execution.py -q`
2. `pytest tests/test_governed_repair_foundation.py -q`
3. `pytest tests/test_contracts.py -q`

## Scope exclusions
- Do not introduce new systems or alter system ownership definitions.
- Do not weaken schema validation or fail-closed behavior.
- Do not add prompt-driven decision branches.
- Do not modify unrelated prompt queue or roadmap modules.

## Dependencies
- Existing governed repair foundation contracts and builders (execution_failure_packet, bounded_repair_candidate_artifact, cde_repair_continuation_input, tpa_repair_gating_input) must remain authoritative.
- Existing AUT-05/AUT-07/AUT-10 slice registry entries and fixture artifacts must remain the real failure basis.
