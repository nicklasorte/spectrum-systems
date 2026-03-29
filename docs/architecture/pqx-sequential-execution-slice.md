# PQX Sequential Execution Slice (PQX-QUEUE-RUN-02)

## Scope
This slice adds a **narrow deterministic bridge** from single-slice execution to ordered sequential execution for a small batch (2–3 slices).

Out of scope for this slice:
- parallelism
- generalized N-scale optimization
- schedulers/workers/distributed orchestration

## Canonical artifact
`prompt_queue_sequence_run` is the persisted source of truth for sequence execution state.

Key fields:
- `queue_run_id`, `run_id`, `trace_id`
- `requested_slice_ids`, `completed_slice_ids`, `failed_slice_ids`
- `current_slice_id`, `prior_slice_ref`, `next_slice_ref`
- `execution_history[]`
- `blocked_reason`, `resume_token`

The artifact is strict (`additionalProperties: false`) and requires provenance-bearing identifiers. No defaults mask missing required identity.

## Execution semantics
- Slice requests are executed in declared order.
- State is persisted and schema-validated before and after each slice transition.
- Execution is fail-closed and stops immediately on first failed slice or continuity violation.
- Resume loads persisted state and continues from the next pending slice.
- Completed slices are not rerun by default.

## Continuity rules
For every execution record in `execution_history`:
1. `queue_run_id` must match the batch `queue_run_id`.
2. `run_id` must remain stable for the whole batch.
3. `trace_id` must match the declared trace for that slice.
4. `parent_execution_ref` must point to the prior slice execution record (or `null` for first slice).
5. `completed_slice_ids` and `failed_slice_ids` must match the statuses in `execution_history`.

Persisted state reload mismatch is treated as a hard error.

## CLI behavior
`scripts/run_prompt_queue_sequence.py` supports:
- sequential run from a list of ordered slice requests
- resume from persisted state (`--resume`)

Exit behavior:
- returns `0` only when status is `completed`
- returns non-zero on failures, blocked conditions, or partial/running state
