# Plan — BATCH-GOV-A — 2026-04-09

## Prompt type
BUILD

## Roadmap item
BATCH-GOV-A

## Objective
Enforce fail-closed PQX post-execution governance so execution records always enter RQX review, fix execution is TPA-gated before PQX, and unresolved review outcomes terminate in operator handoff.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-GOV-A-2026-04-09.md | CREATE | Required plan-first declaration for multi-file governance changes. |
| spectrum_systems/modules/runtime/pqx_slice_runner.py | MODIFY | Emit review_request_artifact for every pqx_slice_execution_record and invoke RQX review. |
| spectrum_systems/modules/runtime/pqx_bundle_orchestrator.py | MODIFY | Emit review_request_artifact for every pqx_bundle_execution_record and invoke RQX review. |
| spectrum_systems/modules/review_queue_executor.py | MODIFY | Restrict RQX outputs to allowed artifact set and emit operator handoff for unresolved non-fix-ready reviews. |
| spectrum_systems/modules/review_fix_execution_loop.py | MODIFY | Enforce TPA-mediated PQX entry guard and tighten non-direct RQX->PQX execution checks. |
| tests/test_review_queue_executor.py | MODIFY | Add/adjust tests for RQX output locking and unresolved operator handoff emission. |
| tests/test_review_fix_execution_loop.py | MODIFY | Add/adjust tests for TPA-gated fix routing and non-TPA rejection. |
| tests/test_pqx_slice_runner.py | MODIFY | Add test ensuring PQX slice execution emits/executes RQX review request. |
| tests/test_pqx_bundle_orchestrator.py | MODIFY | Add test ensuring PQX bundle execution emits/executes RQX review request. |
| docs/architecture/autonomous_execution_loop.md | MODIFY | Minimal clarification: RQX does not execute, TPA gates fixes, unresolved handoff is terminal. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_review_queue_executor.py`
2. `pytest tests/test_review_fix_execution_loop.py`
3. `pytest tests/test_pqx_slice_runner.py`
4. `pytest tests/test_pqx_bundle_orchestrator.py`

## Scope exclusions
- Do not add new subsystems or long-lived services.
- Do not redesign contract schemas.
- Do not alter unrelated orchestration or roadmap logic.

## Dependencies
- Alignment with `README.md` and `docs/architecture/system_registry.md` canonical boundaries.
