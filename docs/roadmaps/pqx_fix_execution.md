# PQX Fix Execution and Reinsertion Loop

## Fix lifecycle
1. Pending fixes are loaded from `pqx_bundle_state.pending_fix_ids` with status `open|planned|in_progress`.
2. Each fix is normalized into a first-class fix-step payload (`fix_id`, `source_step_id`, `severity`, `action_type`, `target`).
3. Fix-step validity is fail-closed checked against bundle roadmap scope.
4. Fix-step execution runs through the existing PQX sequence backbone (single-slice deterministic execution).
5. Result emits a governed `pqx_fix_execution_record` artifact.
6. Bundle state is updated with deterministic execution outcomes (`executed_fixes`, `failed_fixes`, `fix_artifacts`, `reinsertion_points`) and pending-fix status.
7. Bundle orchestration resumes only when blocking fixes are resolved.

## Insertion rules
- `replace` fixes are inserted at `before_source` position.
- `patch|add` fixes are inserted as `patch_after_source` anchored to the source step.
- Insertion point includes deterministic `ordered_index` and `insert_before_step_id` for replay-stable ordering.

## Failure modes (fail-closed)
Execution blocks when:
- fix payload is malformed,
- source step is missing from roadmap scope,
- fix step id conflicts with roadmap ids,
- fix execution result is malformed,
- fix execution status is `failed|blocked`,
- unresolved blocking fixes remain.

## Replay guarantees
- Pending fix ordering is deterministic (`priority`, then `fix_id`).
- Fix-step ids are stable (`fix-step:<fix_id>`).
- Reinsertion metadata is explicit and recorded per fix.
- Execution emits immutable artifacts and updates state without mutating prior outputs.
- Re-running with the same state and inputs yields identical fix execution records and final state transitions.
