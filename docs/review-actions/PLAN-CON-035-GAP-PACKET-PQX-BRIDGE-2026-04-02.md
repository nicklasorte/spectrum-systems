# Plan — CON-035 Gap Packet → PQX Bridge — 2026-04-02

## Prompt type
PLAN

## Roadmap item
CON-035 — CONTROL SURFACE GAP PACKET → PQX BRIDGE (GOVERNED INGESTION)

## Objective
Make PQX fail closed unless governed control-surface gap packets are provided and consumed as the authoritative gap source for deterministic blocking and ordering.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CON-035-GAP-PACKET-PQX-BRIDGE-2026-04-02.md | CREATE | Record required PLAN before multi-file BUILD/WIRE work. |
| PLANS.md | MODIFY | Register active CON-035 plan in the plan index. |
| spectrum_systems/modules/runtime/control_surface_gap_loader.py | CREATE | Add pure fail-closed loader/validator for control_surface_gap_packet refs. |
| spectrum_systems/modules/runtime/control_surface_gap_to_pqx.py | MODIFY | Consume control_surface_gap_packet as authoritative source and deterministic ordering input. |
| spectrum_systems/modules/runtime/pqx_slice_runner.py | MODIFY | Wire packet ingestion into execution context and enforce fail-closed blocking semantics. |
| scripts/pqx_runner.py | MODIFY | Add pass-through CLI flag for control-surface gap packet reference. |
| tests/test_control_surface_gap_to_pqx.py | MODIFY | Add strict packet-consumption and deterministic ordering tests. |
| tests/test_pqx_slice_runner.py | MODIFY | Add fail-closed packet requirement and BLOCK-decision execution blocking tests. |
| tests/test_control_surface_gap_to_pqx.py | MODIFY | Validate no-duplication behavior and malformed packet failure behavior. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest -q tests/test_control_surface_gap_to_pqx.py`
2. `pytest -q tests/test_pqx_slice_runner.py`
3. `pytest -q tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`
5. `python scripts/run_contract_preflight.py`

## Scope exclusions
- Do not modify control-surface gap extraction logic.
- Do not modify enforcement/obedience/trust-spine producers.
- Do not add heuristic gap detection or fallback reconstruction in PQX.
- Do not redesign PQX orchestration architecture.

## Dependencies
- Existing `control_surface_gap_packet` schema and examples remain authoritative inputs.
- Existing PQX slice-runner fail-closed gates remain in place and are only extended for packet ingestion.
