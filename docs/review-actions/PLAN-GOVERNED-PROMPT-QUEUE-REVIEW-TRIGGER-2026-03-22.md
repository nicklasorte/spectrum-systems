# Plan — Governed Prompt Queue Review Trigger — 2026-03-22

## Prompt type
PLAN

## Roadmap item
Governed Prompt Queue — automatic review triggering slice

## Objective
Implement deterministic, fail-closed automatic review triggering from post-execution and loop-control decisions, including schema-backed trigger artifacts and bounded review child work-item creation.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| contracts/schemas/prompt_queue_review_trigger.schema.json | CREATE | Add contract-first schema for review trigger artifact |
| contracts/examples/prompt_queue_review_trigger.json | CREATE | Add golden-path example artifact for review trigger |
| contracts/schemas/prompt_queue_work_item.schema.json | MODIFY | Add minimal fields for review trigger artifact linkage and spawned review lineage |
| contracts/schemas/prompt_queue_state.schema.json | MODIFY | Mirror work-item schema updates in queue aggregate schema |
| contracts/examples/prompt_queue_work_item.json | MODIFY | Keep work-item example schema-valid with new fields |
| contracts/examples/prompt_queue_state.json | MODIFY | Keep queue-state example schema-valid with new fields |
| contracts/standards-manifest.json | MODIFY | Register new prompt_queue_review_trigger contract and bump affected versions |
| spectrum_systems/modules/prompt_queue/review_trigger_artifact_io.py | CREATE | Add pure review-trigger artifact validation + IO boundary |
| spectrum_systems/modules/prompt_queue/review_trigger_policy.py | CREATE | Add pure deterministic review-trigger policy module |
| spectrum_systems/modules/prompt_queue/review_trigger_queue_integration.py | CREATE | Add pure deterministic queue mutation + bounded spawn integration |
| spectrum_systems/modules/prompt_queue/queue_models.py | MODIFY | Add minimal work-item fields required by review-trigger integration |
| spectrum_systems/modules/prompt_queue/queue_state_machine.py | MODIFY | Add minimal transitions for review-trigger result states |
| spectrum_systems/modules/prompt_queue/__init__.py | MODIFY | Export review-trigger modules and functions |
| scripts/run_prompt_queue_review_trigger.py | CREATE | Add thin CLI entrypoint for end-to-end review trigger flow |
| tests/test_prompt_queue_review_trigger.py | CREATE | Add focused fail-closed and deterministic behavior tests |
| tests/test_contracts.py | MODIFY | Add review-trigger example validation test |
| docs/reviews/governed_prompt_queue_review_trigger_report.md | CREATE | Delivery implementation report required by prompt |
| PLANS.md | MODIFY | Register this plan in active plans table |

## Contracts touched
- `prompt_queue_review_trigger` (new)
- `prompt_queue_work_item` (additive update)
- `prompt_queue_state` (additive update)
- `contracts/standards-manifest.json` (new contract registration and version bumps)

## Tests that must pass after execution
1. `pytest -q tests/test_prompt_queue_review_trigger.py`
2. `pytest -q tests/test_prompt_queue_loop_control.py tests/test_prompt_queue_next_step.py tests/test_prompt_queue_post_execution.py tests/test_prompt_queue_execution.py tests/test_prompt_queue_execution_gating.py tests/test_prompt_queue_repair_child_creation.py tests/test_prompt_queue_repair_prompt_generation.py tests/test_prompt_queue_review_parsing.py tests/test_prompt_queue_mvp.py`
3. `pytest -q tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
Explicitly list things that are NOT in scope for this plan.

- Do not invoke live review providers.
- Do not add scheduling, retries, or queue prioritization logic.
- Do not implement merge/close automation or PR automation.
- Do not broaden into provider selection or runtime execution.

## Dependencies
List any prior roadmap items that must be complete before this plan can execute.

- Governed prompt queue MVP slices for execution, post-execution, next-step orchestration, and loop-control must already exist.
