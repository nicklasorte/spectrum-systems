# Plan — GOVERNED PROMPT QUEUE POST EXECUTION POLICY — 2026-03-22

## Prompt type
PLAN

## Roadmap item
Prompt Queue — execution-result-triggered review / re-entry policy slice

## Objective
Implement deterministic, fail-closed post-execution policy evaluation that emits a governed decision artifact and applies minimal queue/work-item state updates with full lineage preservation.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| contracts/schemas/prompt_queue_post_execution_decision.schema.json | CREATE | New authoritative contract for post-execution decision artifacts |
| contracts/examples/prompt_queue_post_execution_decision.json | CREATE | Golden-path example for post-execution decision contract |
| contracts/standards-manifest.json | MODIFY | Register new contract and version bumps for touched prompt queue contracts |
| contracts/schemas/prompt_queue_work_item.schema.json | MODIFY | Add post-execution artifact path and new post-execution statuses |
| contracts/schemas/prompt_queue_state.schema.json | MODIFY | Mirror work-item schema updates in queue aggregate contract |
| contracts/examples/prompt_queue_work_item.json | MODIFY | Keep example aligned with updated schema |
| contracts/examples/prompt_queue_state.json | MODIFY | Keep example aligned with updated schema |
| spectrum_systems/modules/prompt_queue/post_execution_policy.py | CREATE | Pure deterministic post-execution policy evaluator |
| spectrum_systems/modules/prompt_queue/post_execution_artifact_io.py | CREATE | Validation + controlled IO for post-execution decision artifacts |
| spectrum_systems/modules/prompt_queue/post_execution_queue_integration.py | CREATE | Pure queue/work-item mutation from post-execution decisions |
| spectrum_systems/modules/prompt_queue/queue_models.py | MODIFY | Add status enum members and new post-execution artifact path |
| spectrum_systems/modules/prompt_queue/queue_state_machine.py | MODIFY | Add legal transitions from executed states to post-execution states |
| spectrum_systems/modules/prompt_queue/__init__.py | MODIFY | Export post-execution modules for repo-native API surface |
| scripts/run_prompt_queue_post_execution.py | CREATE | Thin CLI for evaluation + artifact emission + deterministic queue update |
| tests/test_prompt_queue_post_execution.py | CREATE | Focused deterministic tests for policy, IO, schema, and integration |
| docs/reviews/governed_prompt_queue_post_execution_report.md | CREATE | Mandatory implementation report artifact |
| PLANS.md | MODIFY | Register active plan in table |

## Contracts touched
- `prompt_queue_post_execution_decision` (new, version 1.0.0)
- `prompt_queue_work_item` (version bump)
- `prompt_queue_state` (version bump)
- `contracts/standards-manifest.json` entry/version updates

## Tests that must pass after execution
1. `pytest -q tests/test_prompt_queue_post_execution.py`
2. `pytest -q tests/test_prompt_queue_execution.py tests/test_prompt_queue_execution_gating.py tests/test_prompt_queue_repair_child_creation.py tests/test_prompt_queue_repair_prompt_generation.py tests/test_prompt_queue_review_parsing.py tests/test_prompt_queue_mvp.py`
3. `pytest -q tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`
5. `.codex/skills/contract-boundary-audit/run.sh`
6. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not implement automatic spawning of next repair child from post-execution decisions.
- Do not implement automatic review provider invocation from post-execution decisions.
- Do not implement retry scheduling or automatic re-execution.
- Do not change live execution provider/runtime behavior.
- Do not introduce queue-wide prioritization/scheduling changes.

## Dependencies
- Governed prompt queue controlled execution slice is complete (execution result artifact + executed states).
- Governed prompt queue execution gating slice is complete (gating lineage/policy artifact).
