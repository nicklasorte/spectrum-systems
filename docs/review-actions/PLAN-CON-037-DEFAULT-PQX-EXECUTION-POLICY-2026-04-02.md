# Plan — CON-037 — 2026-04-02

## Prompt type
PLAN

## Roadmap item
CON-037 — Default PQX Execution Policy for Governed Work

## Objective
Make governed merge-intended changes fail closed unless a PQX execution context is explicitly present, while preserving deterministic exploration-only direct execution as non-authoritative.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CON-037-DEFAULT-PQX-EXECUTION-POLICY-2026-04-02.md | CREATE | Required plan-first artifact for this multi-file governance slice. |
| PLANS.md | MODIFY | Register this plan in the active plans table. |
| docs/governance/default_pqx_execution_policy.md | CREATE | Durable repo-native policy artifact for PQX-required governed execution by default. |
| spectrum_systems/modules/runtime/pqx_execution_policy.py | CREATE | Deterministic governed-path classifier and policy evaluator module. |
| scripts/run_contract_preflight.py | MODIFY | Wire PQX execution policy into existing fail-closed preflight seam. |
| tests/test_contract_preflight.py | MODIFY | Add deterministic tests for classifier and policy enforcement outcomes. |
| tests/test_pqx_slice_runner.py | MODIFY | Add regression test confirming valid governed PQX-backed path still passes. |

## Contracts touched
None.

## Tests that must pass after execution

1. `pytest -q tests/test_contract_preflight.py`
2. `pytest -q tests/test_pqx_slice_runner.py`
3. `pytest -q tests/test_done_certification.py`
4. `pytest -q tests/test_sequence_transition_policy.py`
5. `pytest -q tests/test_contracts.py`
6. `pytest -q tests/test_contract_enforcement.py`
7. `python scripts/run_contract_enforcement.py`
8. `python scripts/run_contract_preflight.py --changed-path scripts/run_contract_preflight.py --changed-path spectrum_systems/modules/runtime/pqx_execution_policy.py --changed-path tests/test_contract_preflight.py --changed-path docs/governance/default_pqx_execution_policy.md`
9. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions

- Do not redesign PQX runner architecture or scheduling model.
- Do not alter promotion/certification contract schemas unless strictly required.
- Do not introduce heuristic or prose-dependent classification logic.
- Do not modify unrelated roadmap or orchestration behavior.

## Dependencies

- Existing contract preflight and PQX slice runner fail-closed seams remain available and unchanged in authority.
