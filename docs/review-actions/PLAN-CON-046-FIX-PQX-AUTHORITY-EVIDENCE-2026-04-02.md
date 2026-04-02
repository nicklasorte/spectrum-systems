# Plan — CON-046-FIX — 2026-04-02

## Prompt type
PLAN

## Roadmap item
CON-046-FIX — Emit PQX Authority Evidence for Preflight Compatibility

## Objective
Expose and carry forward schema-valid `pqx_slice_execution_record` authority evidence refs from sequential execution so preflight can consume deterministic authority context without adding new decision logic.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CON-046-FIX-PQX-AUTHORITY-EVIDENCE-2026-04-02.md | CREATE | Required plan artifact for multi-file fix |
| PLANS.md | MODIFY | Register active CON-046-FIX plan |
| spectrum_systems/modules/runtime/pqx_sequential_loop.py | MODIFY | Validate, persist, and propagate `pqx_slice_execution_record` refs as authority evidence |
| tests/test_pqx_sequential_loop.py | MODIFY | Add coverage for execution-record emission/trace refs/preflight-compatible authority propagation |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest -q tests/test_pqx_sequential_loop.py`
2. `pytest -q tests/test_pqx_slice_runner.py`
3. `pytest -q tests/test_contract_preflight.py`
4. `pytest -q tests/test_contracts.py`
5. `pytest -q tests/test_contract_enforcement.py`

## Scope exclusions
- Do not add new artifact types.
- Do not change control decision or enforcement logic.
- Do not add filesystem discovery logic.
- Do not redesign CLI/runtime boundaries.

## Dependencies
- Existing `pqx_slice_execution_record` schema and runner output remain authoritative.
- Existing preflight authority-evidence semantics remain authoritative.
