# Governed Prompt Queue Retry Policy Report

## 1) Intent
This slice introduces deterministic retry governance for a single failed prompt-queue work item. Retry is now explicit and artifact-backed through `prompt_queue_retry_decision`, with bounded retry budget checks and fail-closed queue updates. This slice does **not** add scheduling, backoff, provider redesign, parallel retry, or cross-item retry chaining.

## 2) Architecture
### Contracts
- Added `contracts/schemas/prompt_queue_retry_decision.schema.json` and golden-path `contracts/examples/prompt_queue_retry_decision.json`.
- Registered the contract in `contracts/standards-manifest.json`.
- Extended prompt-queue work-item/state contracts to include:
  - `retry_count` (non-negative integer)
  - `retry_budget` (non-negative integer)
  - `retry_decision_artifact_path` (nullable artifact path)

### Modules
- `retry_policy.py`: pure deterministic eligibility classifier and decision artifact constructor.
- `retry_artifact_io.py`: schema validation and artifact write path (`artifacts/prompt_queue/retry_decisions/`).
- `retry_queue_integration.py`: pure deterministic queue mutation with lineage and budget checks.
- `scripts/run_prompt_queue_retry.py`: thin CLI wiring load → evaluate → write artifact → apply queue mutation.

## 3) Guarantees
- Fail-closed decisions on malformed work items, invalid statuses, unsupported failure reasons, and budget exhaustion.
- Bounded retries via `retry_count < retry_budget` guard.
- No implicit retries; every path flows through a retry decision artifact.
- Duplicate/unbounded retry prevention via status-lineage matching and post-application status transition away from failure state.
- Retry count increments only when `retry_status=retry_allowed` and `retry_action=retry` is successfully applied.

## 4) Tests
`tests/test_prompt_queue_retry.py` proves:
1. Retry allowed under budget.
2. Retry exhausted over budget.
3. Retry blocked for non-retryable failure.
4. Retry blocked for blocked work items.
5. Retry count increments only on retry initiation.
6. Duplicate retry attempt blocked after deterministic state transition.
7. Retry artifact example validates against schema.
8. Queue update is deterministic for identical inputs.

## 5) Failure modes and future slices
Remaining future work outside this slice:
- Time-based retry scheduling/backoff strategy.
- Operator/manual override pathways for exceptional retries.
- Queue-wide coordination when multiple items contend for retry slots.
- Retry telemetry aggregation and policy learning layers.
