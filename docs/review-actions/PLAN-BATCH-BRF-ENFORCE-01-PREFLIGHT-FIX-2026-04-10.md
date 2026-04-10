# Plan — BATCH-BRF-ENFORCE-01-PREFLIGHT-FIX — 2026-04-10

## Prompt type
BUILD

## Roadmap item
BATCH-BRF-ENFORCE-01-PREFLIGHT-FIX

## Objective
Clear contract preflight BLOCK by applying minimum downstream compatibility fixes explicitly identified in preflight reports, without weakening BRF enforcement.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| tests/test_prompt_queue_audit_bundle.py | MODIFY | Add new required execution artifact fields introduced by BRF contract change. |
| tests/test_prompt_queue_post_execution.py | MODIFY | Update compatibility transition expectations for required batch decision linkage. |
| tests/test_prompt_queue_transition_decision.py | MODIFY | Provide required batch decision artifact argument for transition builder tests. |
| outputs/contract_preflight/preflight_pqx_task_wrapper.json | CREATE | Provide governed PQX wrapper context required by preflight enforcement. |
| docs/reviews/brf_enforce_redteam.md | MODIFY | Append targeted preflight-fix diagnosis summary and outcome (if needed). |

## Contracts touched
None (no schema/contract changes in this fix).

## Tests that must pass after execution
1. `pytest tests/test_prompt_queue_audit_bundle.py tests/test_prompt_queue_post_execution.py tests/test_prompt_queue_transition_decision.py`
2. `python scripts/run_contract_preflight.py --execution-context pqx_governed --base-ref 7a866909208874dad52aedd1ec1d82d1c3d49c81 --head-ref 7a22efe88b6f1141760327a616d4256aa8f2a1cb --authority-evidence-ref artifacts/pqx_runs/preflight.pqx_slice_execution_record.json --pqx-wrapper-path outputs/contract_preflight/preflight_pqx_task_wrapper.json --output-dir outputs/contract_preflight`

## Scope exclusions
- Do not change BRF invariant semantics.
- Do not relax contract preflight rules.
- Do not redesign progression or closure authority boundaries.
- Do not modify unrelated modules/tests.

## Dependencies
- Prior BATCH-BRF-ENFORCE-01 commit with BRF invariant wiring.
