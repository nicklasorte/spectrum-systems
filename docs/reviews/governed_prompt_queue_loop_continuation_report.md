# Governed Prompt Queue Loop Continuation Report

## Intent
This patch delivers a narrow continuation slice for the governed prompt queue loop: after findings reentry generates a repair prompt, the system now evaluates continuation eligibility, enforces duplicate-spawn prevention, optionally reuses the existing repair-child creation path, emits a continuation artifact, and applies deterministic queue/work-item updates.

Delivered now:
- deterministic continuation decisioning and fail-closed validation
- child spawn reuse through existing `spawn_repair_child_in_queue`
- continuation artifact contract + IO boundary
- deterministic queue integration for spawned and blocked/not-needed outcomes
- thin CLI orchestration for one work item

Deferred intentionally:
- retries and retry scheduling
- blocked-item recovery workflows
- queue-wide scheduling/orchestration
- provider abstraction or invocation changes
- downstream automation and PR/live execution expansion

## Architecture

### Contracts and examples
- Added `prompt_queue_loop_continuation` schema + example and registered it in standards manifest.
- Added nullable `loop_continuation_artifact_path` to work-item/state contracts for lineage linkage.

### Continuation validation and decision module
- `spectrum_systems/modules/prompt_queue/loop_continuation.py`
- Pure validation + policy module that:
  - validates findings reentry, repair prompt, and optional loop control artifacts
  - validates lineage consistency against the active work item
  - blocks duplicate continuation when an identical repair prompt already spawned a child
  - blocks continuation when loop control action is not `allow_reentry`
  - reuses existing child creation integration only after all checks pass
  - emits canonical status/reason outcomes (`child_spawned`, `continuation_blocked`, `continuation_not_needed`, `continuation_failed`)

### Artifact validation/IO
- `spectrum_systems/modules/prompt_queue/loop_continuation_artifact_io.py`
- Pure boundary for schema validation and deterministic artifact write path under `artifacts/prompt_queue/loop_continuations/`.

### Queue mutation/integration
- `spectrum_systems/modules/prompt_queue/loop_continuation_queue_integration.py`
- Deterministic queue integration that:
  - requires schema-valid continuation artifacts
  - refuses queue mutation for `continuation_failed`
  - attaches `loop_continuation_artifact_path` exactly once (duplicate guarded)
  - validates spawned-child linkage when continuation spawned a child
  - keeps blocked/not-needed updates minimal (no child payload allowed)

### Thin CLI
- `scripts/run_prompt_queue_loop_continuation.py`
- Flow:
  1. load queue state and target work item
  2. load required findings reentry + repair prompt artifacts and optional loop control artifact
  3. run continuation policy
  4. write continuation artifact
  5. apply queue integration
  6. persist queue state
  7. exit non-zero on validation/integration failures

### Minimal state-model changes
- Added only one new nullable linkage field to work items/state:
  - `loop_continuation_artifact_path`
- No lifecycle redesign, no loop-control tuple changes, no repair-child creation redesign.

## Guarantees
1. Only lineage-valid reentry-generated repair prompts can continue the loop.
2. Blocked loop-control decisions prevent child spawn.
3. Duplicate continuation attempts are prevented for identical repair prompt context.
4. Continuation artifacts are schema-validated before write.
5. Queue/work-item updates are deterministic and fail closed on invalid lineage, duplicates, invalid state, child creation failure, and invalid artifact payloads.

## Tests and guarantee mapping
- `test_valid_reentry_generated_repair_prompt_allowed_continuation_spawns_child`
  - proves happy-path spawn and deterministic queue linkage
- `test_loop_control_blocked_returns_continuation_blocked_and_no_child`
  - proves loop-control block enforcement
- `test_duplicate_continuation_attempt_is_prevented`
  - proves duplicate-spawn prevention
- `test_missing_repair_prompt_artifact_fails_closed`
  - proves fail-closed missing repair prompt artifact
- `test_missing_reentry_artifact_fails_closed`
  - proves fail-closed missing reentry artifact
- `test_lineage_mismatch_between_reentry_and_repair_prompt_fails_closed`
  - proves lineage mismatch denial
- `test_child_creation_failure_returns_continuation_failed`
  - proves failure path classification when child creation cannot proceed
- `test_continuation_example_validates_against_schema`
  - proves contract/example validity
- `test_queue_work_item_updates_are_deterministic_and_schema_valid`
  - proves deterministic + schema-valid queue/work-item updates
- `test_continuation_failed_cannot_mutate_queue`
  - proves fail-closed queue mutation denial on continuation failure

## Failure modes and remaining gaps
Explicitly deferred:
- retry logic for failed continuation or failed spawn
- recovery workflow for blocked continuation artifacts
- queue-level scheduler/orchestrator behavior
- provider abstraction expansion
- downstream automation and live execution coupling
