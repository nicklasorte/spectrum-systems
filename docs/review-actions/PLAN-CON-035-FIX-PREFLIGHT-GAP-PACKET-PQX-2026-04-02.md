# Plan — CON-035 Fix Preflight Gap-Packet PQX — 2026-04-02

## Prompt type
PLAN

## Roadmap item
CON-035-FIX — Preflight classification and required-test mapping alignment for control_surface_gap_packet → PQX bridge.

## Objective
Restore deterministic preflight ALLOW behavior for CON-035 changed-path scenarios by explicitly classifying and mapping required evaluation tests for new governed PQX/control-surface seams while preserving strict fail-closed runtime semantics.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CON-035-FIX-PREFLIGHT-GAP-PACKET-PQX-2026-04-02.md | CREATE | Required PLAN artifact for this multi-file fix slice. |
| PLANS.md | MODIFY | Register active CON-035 fix plan. |
| scripts/run_contract_preflight.py | MODIFY | Add deterministic classification and required test mapping for CON-035 governed paths/artifact expectations. |
| tests/test_contract_preflight.py | MODIFY | Add targeted tests proving ALLOW with required mapping and BLOCK when mapping missing. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest -q tests/test_contract_preflight.py`
2. `pytest -q tests/test_control_surface_gap_to_pqx.py`
3. `pytest -q tests/test_pqx_slice_runner.py`
4. `pytest -q tests/test_contracts.py tests/test_contract_enforcement.py`
5. `python scripts/run_contract_enforcement.py`
6. `python scripts/run_contract_preflight.py --changed-path ...` for CON-035 paths with status passed and strategy_gate_decision ALLOW.

## Scope exclusions
- Do not redesign PQX runtime behavior.
- Do not weaken fail-closed handling for missing/malformed control_surface_gap_packet.
- Do not modify gap extraction logic.
- Do not introduce heuristic classification or fuzzy test mapping.

## Dependencies
- Existing contract preflight report and artifact schemas remain authoritative.
- Existing CON-035 runtime fail-closed behavior remains intact.
