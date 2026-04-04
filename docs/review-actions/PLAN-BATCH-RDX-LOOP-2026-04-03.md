# Plan — BATCH-RDX-LOOP — 2026-04-03

## Prompt type
PLAN

## Roadmap item
BATCH-RDX-LOOP

## Objective
Add deterministic, rule-based cross-batch continuation governance that emits a batch continuation record, gates execution via explicit stop/continue/escalate rules, propagates continuation outcomes into roadmap progress and operator artifacts, and validates deterministic sequencing across runs.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-RDX-LOOP-2026-04-03.md | CREATE | Required plan-first artifact for multi-file governed build |
| PLANS.md | MODIFY | Register active plan entry for BATCH-RDX-LOOP |
| contracts/schemas/batch_continuation_record.schema.json | CREATE | Contract-first schema for deterministic continuation record artifact |
| contracts/examples/batch_continuation_record.json | CREATE | Golden-path example payload for continuation record |
| contracts/schemas/roadmap_multi_batch_run_result.schema.json | MODIFY | Add continuation record list and decision vocabulary alignment |
| contracts/examples/roadmap_multi_batch_run_result.json | MODIFY | Keep example aligned with updated run-result contract |
| contracts/schemas/roadmap_progress_update.schema.json | MODIFY | Add continuation decision summary fields to roadmap progress artifact |
| contracts/examples/roadmap_progress_update.json | MODIFY | Keep roadmap progress example aligned with continuation fields |
| contracts/schemas/build_summary.schema.json | MODIFY | Add continuation decision / stop reason / next candidate fields for operator readability |
| contracts/schemas/next_step_recommendation.schema.json | MODIFY | Add continuation decision / stop reason / next candidate fields for operator readability |
| contracts/examples/build_summary.json | MODIFY | Keep example aligned with new continuation output fields |
| contracts/examples/next_step_recommendation.json | MODIFY | Keep example aligned with new continuation output fields |
| contracts/standards-manifest.json | MODIFY | Register new contract and version bumps for changed schemas |
| spectrum_systems/modules/runtime/roadmap_multi_batch_executor.py | MODIFY | Implement deterministic should_continue_execution rules, batch_execution_gate, continuation record emission |
| spectrum_systems/modules/runtime/system_cycle_operator.py | MODIFY | Surface continuation decision details into build summary and next-step recommendation |
| tests/test_roadmap_multi_batch_executor.py | MODIFY | Add deterministic continuation/stop/escalate and stable sequence coverage |
| tests/test_system_cycle_operator.py | MODIFY | Verify operator artifacts expose continuation decision/stop/next candidate |
| tests/test_contracts.py | MODIFY | Add coverage for new batch_continuation_record contract example validation |

## Contracts touched
- `contracts/schemas/batch_continuation_record.schema.json` (new)
- `contracts/schemas/roadmap_multi_batch_run_result.schema.json`
- `contracts/schemas/roadmap_progress_update.schema.json`
- `contracts/schemas/build_summary.schema.json`
- `contracts/schemas/next_step_recommendation.schema.json`
- `contracts/standards-manifest.json`

## Tests that must pass after execution
1. `pytest tests/test_roadmap_multi_batch_executor.py`
2. `pytest tests/test_system_cycle_operator.py`
3. `pytest tests/test_control_loop.py`
4. `pytest tests/test_contracts.py`
5. `pytest tests/test_contract_enforcement.py`
6. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not redesign PQX execution internals.
- Do not change control decision semantics outside explicit continuation gating integration.
- Do not introduce probabilistic or heuristic continuation logic.
- Do not modify unrelated modules outside runtime continuation path and required contract surfaces.

## Dependencies
- Existing RDX-006 bounded multi-batch execution artifacts and tests must remain deterministic and backward-compatible with governed execution flow expectations.
