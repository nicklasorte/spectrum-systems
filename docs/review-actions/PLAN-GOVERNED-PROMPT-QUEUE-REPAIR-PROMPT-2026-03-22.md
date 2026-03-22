# Plan — GOVERNED PROMPT QUEUE REPAIR PROMPT GENERATION — 2026-03-22

## Prompt type
PLAN

## Roadmap item
Governed Prompt Queue — Repair Prompt Generation Slice

## Objective
Implement deterministic, schema-backed repair prompt generation from parsed review findings, fail closed for PASS/malformed findings, and attach generated repair prompt artifacts to queue work items.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-REPAIR-PROMPT-2026-03-22.md | CREATE | Required PLAN artifact before multi-file BUILD work |
| PLANS.md | MODIFY | Register this plan in active plans table |
| contracts/schemas/prompt_queue_repair_prompt.schema.json | CREATE | Canonical repair prompt artifact schema |
| contracts/examples/prompt_queue_repair_prompt.json | CREATE | Golden-path artifact example |
| contracts/schemas/prompt_queue_work_item.schema.json | MODIFY | Add `repair_prompt_artifact_path` and `repair_prompt_generated` status |
| contracts/schemas/prompt_queue_state.schema.json | MODIFY | Keep embedded work-item contract aligned |
| contracts/examples/prompt_queue_work_item.json | MODIFY | Reflect new nullable path/status support |
| contracts/examples/prompt_queue_state.json | MODIFY | Reflect new nullable path/status support |
| contracts/standards-manifest.json | MODIFY | Register new repair prompt contract |
| spectrum_systems/modules/prompt_queue/queue_models.py | MODIFY | Add status and field support for repair prompt linkage |
| spectrum_systems/modules/prompt_queue/queue_state_machine.py | MODIFY | Add deterministic findings_parsed -> repair_prompt_generated transition |
| spectrum_systems/modules/prompt_queue/repair_prompt_generator.py | CREATE | Pure findings-to-bounded-prompt generation logic |
| spectrum_systems/modules/prompt_queue/repair_prompt_artifact_io.py | CREATE | Schema-backed repair prompt artifact validation + IO |
| spectrum_systems/modules/prompt_queue/repair_prompt_queue_integration.py | CREATE | Pure work-item update logic for repair prompt attachment |
| spectrum_systems/modules/prompt_queue/__init__.py | MODIFY | Export new repair prompt module APIs |
| scripts/run_prompt_queue_repair_prompt.py | CREATE | Thin CLI entrypoint for generation + attachment |
| tests/test_prompt_queue_repair_prompt_generation.py | CREATE | Focused generator/contract/queue integration tests |
| tests/test_prompt_queue_mvp.py | MODIFY | Extend state transition coverage for new status |
| tests/test_contracts.py | MODIFY | Ensure new repair prompt example validates |
| docs/reviews/governed_prompt_queue_repair_prompt_report.md | CREATE | Required implementation report artifact |

## Contracts touched
- Create `prompt_queue_repair_prompt` contract.
- Additive updates to `prompt_queue_work_item` and `prompt_queue_state` to support repair prompt linkage/state.
- Update `contracts/standards-manifest.json` with new contract registry entry.

## Tests that must pass after execution
1. `pytest -q tests/test_prompt_queue_repair_prompt_generation.py`
2. `pytest -q tests/test_prompt_queue_review_parsing.py tests/test_prompt_queue_mvp.py`
3. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not implement automatic child repair work item creation.
- Do not trigger live Codex execution.
- Do not implement retry policy or semantic ranking across findings artifacts.
- Do not add queue parallelism or merge/close automation.

## Dependencies
- `docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-MVP-2026-03-22.md` must be complete.
- `docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-REVIEW-PARSING-2026-03-22.md` must be complete.
