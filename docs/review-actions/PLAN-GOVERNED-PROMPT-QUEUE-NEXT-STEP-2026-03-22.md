# Plan — Governed Prompt Queue Next-Step Orchestration — 2026-03-22

## Prompt type
PLAN

## Roadmap item
Governed Prompt Queue — Next-step orchestration from post-execution decision artifacts

## Objective
Implement deterministic, fail-closed next-step orchestration that maps validated post-execution decisions into governed queue actions, writes a validated next-step action artifact, and applies bounded queue/work-item mutations.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| contracts/schemas/prompt_queue_next_step_action.schema.json | CREATE | New contract for orchestration next-step action artifact. |
| contracts/examples/prompt_queue_next_step_action.json | CREATE | Golden-path example for new next-step action contract. |
| contracts/standards-manifest.json | MODIFY | Register new contract and version bump manifest metadata. |
| contracts/schemas/prompt_queue_work_item.schema.json | MODIFY | Add minimal nullable `next_step_action_artifact_path` field. |
| contracts/schemas/prompt_queue_state.schema.json | MODIFY | Mirror work-item schema addition in queue state embedded work item definition. |
| contracts/examples/prompt_queue_work_item.json | MODIFY | Keep example contract-valid with new nullable field. |
| contracts/examples/prompt_queue_state.json | MODIFY | Keep queue example contract-valid with new nullable field. |
| spectrum_systems/modules/prompt_queue/queue_models.py | MODIFY | Add work-item field and defaults for next-step action artifact path. |
| spectrum_systems/modules/prompt_queue/queue_state_machine.py | MODIFY | Add minimal deterministic transitions required by next-step integration. |
| spectrum_systems/modules/prompt_queue/next_step_orchestrator.py | CREATE | Pure mapping + lineage validation from post-execution decision to next-step action. |
| spectrum_systems/modules/prompt_queue/next_step_action_artifact_io.py | CREATE | Pure validation + IO helper for next-step action artifacts. |
| spectrum_systems/modules/prompt_queue/next_step_queue_integration.py | CREATE | Pure deterministic queue mutation and bounded child spawn integration. |
| spectrum_systems/modules/prompt_queue/__init__.py | MODIFY | Export new orchestration APIs. |
| scripts/run_prompt_queue_next_step.py | CREATE | Thin CLI for end-to-end orchestration flow. |
| tests/test_prompt_queue_next_step.py | CREATE | Focused fail-closed and deterministic orchestration tests. |
| docs/reviews/governed_prompt_queue_next_step_report.md | CREATE | Required implementation delivery report artifact. |
| PLANS.md | MODIFY | Register this plan in active plans table. |

## Contracts touched
- `prompt_queue_next_step_action` (new schema and example)
- `prompt_queue_work_item` (additive field)
- `prompt_queue_state` (embedded additive field)
- `standards_manifest` (version record update)

## Tests that must pass after execution
1. `pytest -q tests/test_prompt_queue_next_step.py`
2. `pytest -q tests/test_prompt_queue_post_execution.py tests/test_prompt_queue_execution.py tests/test_prompt_queue_execution_gating.py tests/test_prompt_queue_repair_child_creation.py tests/test_prompt_queue_repair_prompt_generation.py tests/test_prompt_queue_review_parsing.py tests/test_prompt_queue_mvp.py`
3. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`
5. `.codex/skills/contract-boundary-audit/run.sh`
6. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not implement retries or retry scheduling.
- Do not implement queue-wide prioritization/scheduling.
- Do not implement live provider execution.
- Do not implement merge/close automation or PR automation.
- Do not redesign approval UX.
- Do not run parallel orchestration.

## Dependencies
- `docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-POST-EXECUTION-2026-03-22.md` must be complete.
- `docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-CONTROLLED-EXECUTION-2026-03-22.md` must be complete.
