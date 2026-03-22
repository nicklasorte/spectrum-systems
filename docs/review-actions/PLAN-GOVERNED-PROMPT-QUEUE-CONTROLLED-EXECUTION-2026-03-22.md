# Plan — GOVERNED-PROMPT-QUEUE-CONTROLLED-EXECUTION — 2026-03-22

## Prompt type
PLAN

## Roadmap item
Governed Prompt Queue — bounded controlled execution MVP

## Objective
Implement deterministic, fail-closed controlled execution for `runnable` work items with gating re-validation at execution entry, an `executing` guard state, and schema-backed execution result artifacts.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-CONTROLLED-EXECUTION-2026-03-22.md | CREATE | Required plan artifact before multi-file BUILD work. |
| PLANS.md | MODIFY | Register active plan in repository plan index. |
| contracts/schemas/prompt_queue_execution_result.schema.json | CREATE | Contract for controlled execution result artifacts. |
| contracts/examples/prompt_queue_execution_result.json | CREATE | Golden-path example for execution result contract. |
| contracts/schemas/prompt_queue_work_item.schema.json | MODIFY | Add execution result linkage and execution statuses. |
| contracts/schemas/prompt_queue_state.schema.json | MODIFY | Mirror work-item execution updates in queue schema. |
| contracts/examples/prompt_queue_work_item.json | MODIFY | Keep work item example aligned to contract changes. |
| contracts/examples/prompt_queue_state.json | MODIFY | Keep queue state example aligned to contract changes. |
| contracts/standards-manifest.json | MODIFY | Register new contract and version bumps for touched contracts. |
| spectrum_systems/modules/prompt_queue/queue_models.py | MODIFY | Add execution status values and execution result path field. |
| spectrum_systems/modules/prompt_queue/queue_state_machine.py | MODIFY | Add minimal deterministic execution transitions with `executing` guard state. |
| spectrum_systems/modules/prompt_queue/execution_artifact_io.py | CREATE | Pure execution-result artifact validation and write boundary. |
| spectrum_systems/modules/prompt_queue/execution_runner.py | CREATE | Pure deterministic simulated execution logic with gating re-validation. |
| spectrum_systems/modules/prompt_queue/execution_queue_integration.py | CREATE | Pure queue mutation and duplicate-prevention integration for execution lifecycle. |
| spectrum_systems/modules/prompt_queue/__init__.py | MODIFY | Export controlled execution interfaces. |
| scripts/run_prompt_queue_execution.py | CREATE | Thin CLI to run one controlled execution attempt. |
| tests/test_prompt_queue_execution.py | CREATE | Focused tests for controlled execution guarantees and failure modes. |
| docs/reviews/governed_prompt_queue_controlled_execution_report.md | CREATE | Mandatory implementation report artifact for delivery. |

## Contracts touched
- `prompt_queue_execution_result` (new)
- `prompt_queue_work_item` (additive)
- `prompt_queue_state` (additive)
- `contracts/standards-manifest.json` version registry entry updates

## Tests that must pass after execution
1. `pytest -q tests/test_prompt_queue_execution.py`
2. `pytest -q tests/test_prompt_queue_execution_gating.py tests/test_prompt_queue_repair_child_creation.py tests/test_prompt_queue_repair_prompt_generation.py tests/test_prompt_queue_review_parsing.py tests/test_prompt_queue_mvp.py`
3. `pytest -q tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not implement live provider execution.
- Do not add retries, scheduling, rollback, or parallel execution.
- Do not build a full reconciliation engine.
- Do not change merge/close automation or approval UX.

## Dependencies
- `docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-EXECUTION-GATING-2026-03-22.md` outputs must be available (runnable gating artifacts + lineage fields).
