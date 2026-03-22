# Plan — GOVERNED-PROMPT-QUEUE-EXECUTION-GATING — 2026-03-22

## Prompt type
PLAN

## Roadmap item
Governed Prompt Queue — execution gating and repair-loop control policy

## Objective
Add deterministic, contract-first execution gating so repair child work items cannot proceed without schema-valid lineage, bounded generation depth, and explicit approval policy outcomes.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-EXECUTION-GATING-2026-03-22.md | CREATE | Required plan artifact before multi-file BUILD work. |
| PLANS.md | MODIFY | Register active plan in repository plan index. |
| contracts/schemas/prompt_queue_execution_gating_decision.schema.json | CREATE | Contract for schema-backed execution gating decision artifact. |
| contracts/examples/prompt_queue_execution_gating_decision.json | CREATE | Golden example for execution gating decision contract. |
| contracts/schemas/prompt_queue_work_item.schema.json | MODIFY | Add gating linkage/state fields and minimal state expansion. |
| contracts/schemas/prompt_queue_state.schema.json | MODIFY | Mirror work-item schema updates in queue aggregate schema. |
| contracts/standards-manifest.json | MODIFY | Publish new contract and version bumps for touched contracts. |
| spectrum_systems/modules/prompt_queue/queue_models.py | MODIFY | Add queue/work-item fields and status/risk enums required for gating. |
| spectrum_systems/modules/prompt_queue/queue_state_machine.py | MODIFY | Add deterministic transitions for execution gating lifecycle statuses. |
| spectrum_systems/modules/prompt_queue/execution_gating_artifact_io.py | CREATE | Pure schema validation/IO boundary for gating decision artifacts. |
| spectrum_systems/modules/prompt_queue/execution_gating_policy.py | CREATE | Pure deterministic gating policy evaluator and decision artifact builder. |
| spectrum_systems/modules/prompt_queue/execution_gating_queue_integration.py | CREATE | Pure queue/work-item mutation logic driven by validated gating decisions. |
| spectrum_systems/modules/prompt_queue/__init__.py | MODIFY | Export execution gating module interfaces for repo-native usage. |
| scripts/run_prompt_queue_execution_gating.py | CREATE | Thin CLI entrypoint for gating evaluation + queue update. |
| contracts/examples/prompt_queue_work_item.json | MODIFY | Keep canonical example aligned with schema updates. |
| contracts/examples/prompt_queue_state.json | MODIFY | Keep canonical queue example aligned with schema updates. |
| tests/test_prompt_queue_execution_gating.py | CREATE | Focused policy + queue integration tests for fail-closed gating behavior. |
| docs/reviews/governed_prompt_queue_execution_gating_report.md | CREATE | Mandatory implementation report artifact for this delivery. |

## Contracts touched
- `prompt_queue_execution_gating_decision` (new)
- `prompt_queue_work_item` (additive)
- `prompt_queue_state` (additive)
- `contracts/standards-manifest.json` version registry entry updates

## Tests that must pass after execution
1. `pytest -q tests/test_prompt_queue_execution_gating.py`
2. `pytest -q tests/test_prompt_queue_repair_child_creation.py tests/test_prompt_queue_repair_prompt_generation.py tests/test_prompt_queue_mvp.py`
3. `pytest -q tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not implement automatic execution of runnable work items.
- Do not implement retry scheduling or cross-item prioritization.
- Do not implement approval UI beyond explicit inputs.
- Do not redesign general policy engine infrastructure.

## Dependencies
- `docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-REPAIR-CHILD-CREATION-2026-03-22.md` must be complete enough to provide child lineage fields consumed by gating.
