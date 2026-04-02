# Plan — CON-047 — 2026-04-02

## Prompt type
PLAN

## Roadmap item
CON-047 — Authoritative PQX Execution Trace Artifact

## Objective
Make sequential PQX execution emit a single schema-backed authoritative trace artifact that unifies per-slice refs/results fail-closed without changing decision semantics.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CON-047-AUTHORITATIVE-PQX-EXECUTION-TRACE-2026-04-02.md | CREATE | Required PLAN artifact before multi-file BUILD + contract changes |
| PLANS.md | MODIFY | Register active CON-047 plan in plan ledger |
| contracts/schemas/pqx_sequential_execution_trace.schema.json | CREATE | Add authoritative schema-backed trace contract |
| contracts/examples/pqx_sequential_execution_trace.json | CREATE | Add canonical example payload for the new trace contract |
| contracts/standards-manifest.json | MODIFY | Pin new contract in standards registry |
| spectrum_systems/modules/runtime/pqx_sequential_loop.py | MODIFY | Emit authoritative trace artifact with required refs and fail-closed validation |
| scripts/run_pqx_sequence.py | MODIFY | Keep CLI thin while validating/surfacing authoritative trace artifact |
| tests/test_pqx_execution_trace.py | CREATE | Focused coverage for trace contract and fail-closed semantics |
| tests/test_pqx_sequential_loop.py | MODIFY | Align loop assertions with authoritative trace semantics |
| tests/test_contracts.py | MODIFY | Add trace contract example validation |

## Contracts touched
- `pqx_sequential_execution_trace` (new contract)
- `standards_manifest` (version pin update for new contract)

## Tests that must pass after execution
1. `pytest -q tests/test_pqx_execution_trace.py`
2. `pytest -q tests/test_pqx_sequential_loop.py`
3. `pytest -q tests/test_pqx_sequence_runner.py`
4. `pytest -q tests/test_contracts.py`
5. `pytest -q tests/test_contract_enforcement.py`
6. `python scripts/run_contract_enforcement.py`
7. `python scripts/run_contract_preflight.py --changed-path contracts/schemas/pqx_sequential_execution_trace.schema.json --changed-path contracts/examples/pqx_sequential_execution_trace.json --changed-path contracts/standards-manifest.json --changed-path spectrum_systems/modules/runtime/pqx_sequential_loop.py --changed-path scripts/run_pqx_sequence.py --changed-path tests/test_pqx_execution_trace.py --changed-path tests/test_pqx_sequential_loop.py --changed-path tests/test_contracts.py`

## Scope exclusions
- Do not change control-loop decision logic.
- Do not change enforcement semantics.
- Do not introduce a parallel trace taxonomy.
- Do not redesign observability outputs.

## Dependencies
- CON-046 sequential loop seam is already established and remains the execution backbone.
- Existing `pqx_slice_execution_record`, replay, eval decision, and enforcement artifacts remain authoritative source seams referenced by trace.
