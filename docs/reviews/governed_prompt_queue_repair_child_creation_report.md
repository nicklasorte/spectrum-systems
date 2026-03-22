# Governed Prompt Queue Repair Child Creation Report

## Date
2026-03-22

## Scope
This patch delivers governed child repair work-item creation from validated repair prompt artifacts, including deterministic queue mutation, duplicate-spawn prevention, explicit lineage preservation, and a thin CLI entrypoint for controlled invocation.

## Files created/changed
- `docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-REPAIR-CHILD-CREATION-2026-03-22.md`
- `PLANS.md`
- `contracts/schemas/prompt_queue_work_item.schema.json`
- `contracts/schemas/prompt_queue_state.schema.json`
- `contracts/examples/prompt_queue_work_item.json`
- `contracts/examples/prompt_queue_state.json`
- `contracts/standards-manifest.json`
- `spectrum_systems/modules/prompt_queue/queue_models.py`
- `spectrum_systems/modules/prompt_queue/queue_state_machine.py`
- `spectrum_systems/modules/prompt_queue/repair_child_creator.py`
- `spectrum_systems/modules/prompt_queue/repair_child_queue_integration.py`
- `spectrum_systems/modules/prompt_queue/__init__.py`
- `scripts/run_prompt_queue_repair_child.py`
- `tests/test_prompt_queue_repair_child_creation.py`
- `tests/test_prompt_queue_mvp.py`

## Child-work-item lineage summary
- Child creation requires a schema-valid repair prompt artifact and verifies parent/artifact identity alignment (`repair_prompt.work_item_id == parent.work_item_id`).
- Child records explicit lineage fields:
  - `parent_work_item_id`
  - `spawned_from_repair_prompt_artifact_path`
  - `spawned_from_findings_artifact_path`
  - `spawned_from_review_artifact_path`
  - `repair_loop_generation`
- Parent records `child_work_item_ids` deterministically and transitions from `repair_prompt_generated` to `repair_child_created`.

## Duplicate-prevention guarantees
- Queue integration performs explicit duplicate detection keyed by:
  - `parent_work_item_id`
  - `spawned_from_repair_prompt_artifact_path`
- If a match is found, creation fails closed with an error and does not mutate queue state.

## Test evidence
- `pytest -q tests/test_prompt_queue_repair_child_creation.py` (new focused child-spawn coverage)
- `pytest -q tests/test_prompt_queue_repair_prompt_generation.py`
- `pytest -q tests/test_prompt_queue_review_parsing.py`
- `pytest -q tests/test_prompt_queue_mvp.py`
- `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
- `python scripts/run_contract_enforcement.py`
- `.codex/skills/contract-boundary-audit/run.sh` (fails with existing repository-wide warnings/violations unrelated to this patch)
- `pytest -q` (full suite)

## Remaining gaps
Out of scope and intentionally not delivered in this patch:
- automatic execution of spawned child repair prompts
- retry policies and maximum repair-loop limits
- dependency scheduling across queue items
- queue parallelism/orchestration policy
- merge/close automation
- semantic deduplication and auto-prioritization across similar repair prompts
