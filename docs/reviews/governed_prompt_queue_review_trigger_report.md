# Governed Prompt Queue Review Trigger Report

## Date
2026-03-22

## Scope
Implement deterministic automatic review triggering for governed prompt queue work items based on post-execution and loop-control decision artifacts, including schema-backed trigger artifact generation, bounded review child creation, and fail-closed queue integration.

## Files created/changed
- `contracts/schemas/prompt_queue_review_trigger.schema.json` (created)
- `contracts/examples/prompt_queue_review_trigger.json` (created)
- `contracts/schemas/prompt_queue_work_item.schema.json` (changed)
- `contracts/schemas/prompt_queue_state.schema.json` (changed)
- `contracts/examples/prompt_queue_work_item.json` (changed)
- `contracts/examples/prompt_queue_state.json` (changed)
- `contracts/standards-manifest.json` (changed)
- `spectrum_systems/modules/prompt_queue/review_trigger_policy.py` (created)
- `spectrum_systems/modules/prompt_queue/review_trigger_artifact_io.py` (created)
- `spectrum_systems/modules/prompt_queue/review_trigger_queue_integration.py` (created)
- `spectrum_systems/modules/prompt_queue/queue_models.py` (changed)
- `spectrum_systems/modules/prompt_queue/queue_state_machine.py` (changed)
- `spectrum_systems/modules/prompt_queue/__init__.py` (changed)
- `scripts/run_prompt_queue_review_trigger.py` (created)
- `tests/test_prompt_queue_review_trigger.py` (created)
- `tests/test_contracts.py` (changed)

## Review-trigger policy summary
- Re-validates work item schema, post-execution decision artifact schema, and loop-control decision artifact schema before any trigger decision.
- Enforces lineage checks across work item ID, parent lineage, and artifact path consistency.
- Deterministic mapping:
  - `review_required` + loop-control permitting review (`allow_reentry`/`require_review`/absent) => `review_triggered`
  - `complete` => `no_review_needed`
  - `reentry_blocked` => `blocked_no_trigger`
  - loop-control `block_reentry` => `blocked_no_trigger`
  - malformed artifacts/lineage mismatch => `blocked_no_trigger`
- Emits schema-validated review-trigger artifact with required lineage fields plus optional warnings/blocking conditions.

## State-model changes
- Added work-item status `review_triggered`.
- Added minimal transition support:
  - `review_required -> review_triggered`
  - `review_required -> blocked`
  - `reentry_blocked -> blocked`
- Added nullable work-item lineage fields:
  - `review_trigger_artifact_path`
  - `spawned_from_execution_result_artifact_path`
  - `spawned_from_post_execution_decision_artifact_path`
  - `spawned_from_loop_control_decision_artifact_path`

## Test evidence
- Added focused test suite `tests/test_prompt_queue_review_trigger.py` covering trigger policy, fail-closed behavior, duplicate prevention, deterministic queue updates, and schema validity.
- Added `tests/test_contracts.py` coverage for `prompt_queue_review_trigger` example validation.

## Remaining gaps
- Live review-provider invocation remains out of scope.
- Retry policy and scheduling remain out of scope.
- Queue-wide prioritization/scheduling remains out of scope.
- Merge/close flow automation remains out of scope.
- PR automation remains out of scope.
