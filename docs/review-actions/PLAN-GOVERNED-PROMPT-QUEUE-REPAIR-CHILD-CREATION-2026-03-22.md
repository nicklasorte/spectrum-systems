# Plan — Governed Prompt Queue Repair Child Creation — 2026-03-22

## Prompt type
PLAN

## Roadmap item
Prompt B-BUILD slice extension — Governed Prompt Queue repair-loop child creation

## Objective
Implement deterministic, fail-closed child repair work-item creation from validated FAIL repair prompt artifacts with explicit lineage and duplicate prevention.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-REPAIR-CHILD-CREATION-2026-03-22.md | CREATE | Record required PLAN before BUILD work. |
| PLANS.md | MODIFY | Register this plan in active plans table. |
| contracts/schemas/prompt_queue_work_item.schema.json | MODIFY | Add minimal child-repair lineage fields for spawned child tracking and duplicate prevention keys. |
| contracts/schemas/prompt_queue_state.schema.json | MODIFY | Keep queue aggregate work-item schema in sync with work-item contract. |
| contracts/examples/prompt_queue_work_item.json | MODIFY | Update golden example with new optional lineage fields. |
| contracts/examples/prompt_queue_state.json | MODIFY | Update golden queue example to include revised work-item shape. |
| contracts/standards-manifest.json | MODIFY | Version-bump touched contracts per contract authority rules. |
| spectrum_systems/modules/prompt_queue/queue_models.py | MODIFY | Extend work-item model and status enum for minimal repair-child lifecycle support. |
| spectrum_systems/modules/prompt_queue/repair_child_creator.py | CREATE | Pure constructor/validation module for child work-item creation from repair prompt artifact. |
| spectrum_systems/modules/prompt_queue/repair_child_queue_integration.py | CREATE | Pure queue mutation module to attach child deterministically and prevent duplicates. |
| spectrum_systems/modules/prompt_queue/queue_state_machine.py | MODIFY | Allow minimal justified parent transition to repair child created state. |
| spectrum_systems/modules/prompt_queue/__init__.py | MODIFY | Export new child-creation APIs. |
| scripts/run_prompt_queue_repair_child.py | CREATE | Thin CLI entrypoint for parent+artifact-driven child spawning and queue/work-item persistence. |
| tests/test_prompt_queue_repair_child_creation.py | CREATE | Focused deterministic tests for creation, lineage, duplicate prevention, and fail-closed behavior. |
| tests/test_prompt_queue_mvp.py | MODIFY | Add lifecycle transition coverage for minimal new status. |
| docs/reviews/governed_prompt_queue_repair_child_creation_report.md | CREATE | Delivery implementation report with guarantees, evidence, and remaining gaps. |

## Contracts touched
- `prompt_queue_work_item` (schema update)
- `prompt_queue_state` (schema update)
- `contracts/standards-manifest.json` (version updates)

## Tests that must pass after execution
1. `pytest -q tests/test_prompt_queue_repair_child_creation.py`
2. `pytest -q tests/test_prompt_queue_repair_prompt_generation.py`
3. `pytest -q tests/test_prompt_queue_review_parsing.py`
4. `pytest -q tests/test_prompt_queue_mvp.py`
5. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
6. `python scripts/run_contract_enforcement.py`

## Scope exclusions
Explicitly list things that are NOT in scope for this plan.

- Do not implement automatic Codex execution of child repair prompts.
- Do not add retry policies or repair-loop maximum limits.
- Do not add dependency scheduling or queue parallelism.
- Do not add merge/close automation.
- Do not add semantic deduplication or cross-child prioritization.

## Dependencies
List any prior roadmap items that must be complete before this plan can execute.

- `docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-MVP-2026-03-22.md`
- `docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-REVIEW-PARSING-2026-03-22.md`
- `docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-REPAIR-PROMPT-2026-03-22.md`
