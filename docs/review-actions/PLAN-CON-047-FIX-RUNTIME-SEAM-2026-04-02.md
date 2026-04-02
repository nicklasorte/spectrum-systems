# Plan — CON-047-FIX Runtime Seam Decision Propagation — 2026-04-02

## Prompt type
PLAN

## Roadmap item
CON-047 — Authoritative PQX Execution Trace Artifact

## Objective
Fix the narrow PQX runtime seam so fixture-driven control outcomes (ALLOW/BLOCK/REQUIRE_REVIEW) propagate unchanged through decision emission, enforcement, and sequential trace termination with deterministic decision IDs for identical fixture content.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CON-047-FIX-RUNTIME-SEAM-2026-04-02.md | CREATE | Required plan artifact for a multi-file runtime seam fix |
| PLANS.md | MODIFY | Register this plan in active plans table |
| spectrum_systems/modules/runtime/pqx_slice_runner.py | MODIFY | Remove hardcoded ALLOW control decision emission; derive control decision from replay-driven control-loop contract path |
| spectrum_systems/modules/runtime/pqx_sequential_loop.py | MODIFY | Ensure enforcement consumes emitted control decision artifact directly and trace status reflects true enforced outcome |
| spectrum_systems/modules/runtime/evaluation_control.py | MODIFY | Stabilize decision_id generation for identical fixture decision content |
| tests/test_pqx_sequential_loop.py | MODIFY | Cover BLOCK/REQUIRE_REVIEW/ALLOW stop semantics and trace terminal invariants through the updated seam |
| tests/test_run_pqx_sequence_cli.py | MODIFY | Add deterministic decision-id assertion under repeated identical fixture-mode ALLOW behavior |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest -q tests/test_run_pqx_sequence_cli.py`
2. `pytest -q tests/test_pqx_sequential_loop.py`
3. `pytest -q tests/test_pqx_execution_trace.py`
4. `pytest -q tests/test_contracts.py`
5. `pytest -q tests/test_contract_enforcement.py`

## Scope exclusions
- Do not redesign the control-loop architecture.
- Do not add new artifact types or schemas.
- Do not add parallel decision logic outside existing evaluation/enforcement modules.
- Do not change CLI decision policy beyond consuming sequential trace final_status.

## Dependencies
- Existing CON-046/CON-047 sequential loop and trace contracts remain the governing baseline.
