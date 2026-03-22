# Governed Prompt Queue Live Review Invocation Foundation Report

## Intent
This patch closes the blocking foundation gaps from the surgical review without implementing live provider invocation execution.
It delivers only the minimum safe baseline needed for the next invocation slice: provider-policy correction, invocation-state path, invocation-result contract, persisted linkage for idempotency, and duplicate-invocation guard primitives.

## Architecture

### Provider policy correction (Codex-first, Claude-fallback)
- Updated prompt queue model default so work items are now created with `review_provider_primary: "codex"`.
- Updated contract schemas and examples to enforce/publish the same codex-primary policy.
- Updated fallback orchestration assumptions to request Codex first, then use Claude only as allowed fallback.

### Minimal invocation state path
- Added the smallest invocation lifecycle statuses:
  - `review_invoking`
  - `review_invocation_succeeded`
  - `review_invocation_failed`
- Added only safe transition edges required for this MVP foundation:
  - `review_triggered -> review_invoking`
  - `review_invoking -> review_invocation_succeeded`
  - `review_invoking -> review_invocation_failed`
  - `review_invoking -> blocked` (fail-closed safety path)

### Invocation-result contract
- Added canonical schema:
  - `contracts/schemas/prompt_queue_review_invocation_result.schema.json`
- Added golden-path example:
  - `contracts/examples/prompt_queue_review_invocation_result.json`
- Registered the contract in:
  - `contracts/standards-manifest.json`

### Persisted invocation-result linkage on work item
- Added nullable persisted linkage field:
  - `review_invocation_result_artifact_path`
- Wired this field into:
  - model (`queue_models.py`)
  - work-item schema
  - queue-state embedded work-item schema
  - queue/work-item examples

### Duplicate-invocation guard foundation
- Added pure helper primitives in `review_invocation_guard.py`:
  - `has_duplicate_review_invocation_result(...)`
  - `assert_no_duplicate_review_invocation(...)`
- Guard behavior is bounded to lineage-aware duplicate detection:
  - duplicate when a persisted invocation result exists and stored trigger lineage matches current trigger path.

## Guarantees
- Codex is now the primary review provider for this queue path.
- `review_triggered` now has a legal invocation entry transition path.
- Review invocation results now have a published contract and example.
- Work items now carry persisted invocation-result linkage (`review_invocation_result_artifact_path`) for future idempotency enforcement.

## Validation Evidence
- Focused prompt-queue MVP tests updated and passing.
- Contract validation and enforcement tests updated and passing.
- Contract enforcement script passes with no failures.
- Full repository test suite passes after scope-aligned updates.

## Failure Modes and Gaps Deferred to Next Slice
Out of scope and intentionally deferred:
1. actual live provider invocation calls
2. runtime fallback execution behavior under real provider failures
3. queue mutation on real invocation completion
4. duplicate prevention enforcement during invocation runtime
5. provider output parsing, retries, scheduling

## Blockers
- None for this foundational slice.
