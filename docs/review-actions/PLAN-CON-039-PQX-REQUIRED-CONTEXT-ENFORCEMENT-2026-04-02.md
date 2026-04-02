# Plan — CON-039 — 2026-04-02

## Prompt type
PLAN

## Roadmap item
CON-039 — PQX Required Context Enforcement

## Objective
Introduce deterministic fail-closed enforcement that requires governed work to carry canonical CON-038 wrapper context and valid authority references at preflight/entry seams while preserving explicit non-authoritative exploration posture.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CON-039-PQX-REQUIRED-CONTEXT-ENFORCEMENT-2026-04-02.md | CREATE | Required plan-first artifact for this multi-file enforcement slice. |
| PLANS.md | MODIFY | Register this plan in the active plans table per repository policy. |
| spectrum_systems/modules/runtime/pqx_required_context_enforcement.py | CREATE | Pure deterministic enforcement module for governed PQX context and wrapper compatibility checks. |
| spectrum_systems/modules/runtime/pqx_execution_policy.py | MODIFY | Reuse policy classification/execution context controls and expose context enforcement details. |
| scripts/run_contract_preflight.py | MODIFY | Wire required-context enforcement into contract preflight admission seam and report output. |
| scripts/pqx_runner.py | MODIFY | Wire required-context enforcement into PQX runner entry seam for governed execution admission. |
| tests/test_pqx_required_context_enforcement.py | CREATE | Focused regression tests for governed/context/wrapper fail-closed enforcement behavior. |
| tests/test_contract_preflight.py | MODIFY | Validate preflight integration, deterministic blocking reasons, and machine-readable enforcement output. |

## Contracts touched
None.

## Tests that must pass after execution

1. `pytest -q tests/test_pqx_required_context_enforcement.py`
2. `pytest -q tests/test_contract_preflight.py`
3. `pytest -q tests/test_pqx_slice_runner.py`
4. `pytest -q tests/test_codex_to_pqx_wrapper.py`
5. `pytest -q tests/test_contracts.py`
6. `pytest -q tests/test_contract_enforcement.py`
7. `python scripts/run_contract_enforcement.py`
8. `python scripts/run_contract_preflight.py --changed-path spectrum_systems/modules/runtime/pqx_required_context_enforcement.py --changed-path spectrum_systems/modules/runtime/pqx_execution_policy.py --changed-path scripts/run_contract_preflight.py --changed-path scripts/pqx_runner.py --changed-path tests/test_pqx_required_context_enforcement.py --changed-path tests/test_contract_preflight.py`
9. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions

- Do not redesign PQX architecture, authority model, or wrapper generation logic.
- Do not add heuristic/prose-based posture inference.
- Do not introduce new wrapper contracts or ontology beyond deterministic enforcement signals.
- Do not broaden this slice into queue/orchestrator redesign.

## Dependencies

- CON-036 default PQX execution policy is active.
- CON-037 authority/context policy seam exists and is consumed.
- CON-038 codex_pqx_task_wrapper canonical contract and builder are available.
