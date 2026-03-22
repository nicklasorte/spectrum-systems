# Governed Prompt Queue Live Review Invocation Report

## Intent
This patch delivers the first bounded live review invocation slice for a single `review_triggered` work item.
It enforces strict entry validation and deterministic queue integration through invocation result artifact write/persist/state transitions.

Delivered now:
- strict entry preconditions with lineage re-read from disk
- codex-first invocation with bounded claude fallback
- schema-backed invocation result artifact generation and persistence
- deterministic terminal transitions to `review_invocation_succeeded`, `review_invocation_failed`, or `blocked`

Deferred to later prompts:
- parsing review output
- retries/scheduling
- blocked-item recovery workflows
- queue-wide orchestration
- broader provider abstraction expansion

## Architecture

### Contracts
- Tightened `prompt_queue_review_invocation_result` schema with cross-field invariants:
  - `fallback_used=true` requires bounded non-null `fallback_reason`
  - `fallback_used=false` requires `fallback_reason=null`
  - `invocation_status=success` requires non-null `output_reference`
- Added deterministic `invocation_id` field.

### Entry validation
- `review_invocation_entry_validation.py`
- Performs LI-CR-5 checklist before any invocation transition.
- Re-reads trigger and execution artifacts from disk.

### Provider invocation boundary
- `review_invocation_provider_adapter.py`
- Codex primary, bounded fallback reasons only: usage_limit, rate_limited, auth_failure, timeout, provider_unavailable.
- Fallback is explicit in returned outcome and never silent.

### Invocation runner
- `review_invocation_runner.py`
- Pure execution of entry validation + provider adapter.
- Produces deterministic invocation artifact payload with lineage.

### Artifact IO boundary
- `review_invocation_artifact_io.py`
- Enforces LI-CR-1 and LI-CR-2 pre-write invariants and schema validation.
- Writes artifact under `review_invocation_results` directory.

### Queue integration
- `review_invocation_queue_integration.py`
- Implements required write ordering contract and failure mapping contract.
- Blocks duplicates and fail-closes to `blocked` on invalid lineage/schema/write/update failures.
- Maps provider failure before output to `review_invocation_failed`.

### CLI
- `scripts/run_prompt_queue_live_review_invocation.py`
- Thin single-item entry point over queue integration.

## Guarantees
- Provider calls only occur after strict preconditions and after transition to `review_invoking`.
- Duplicate invocation is prevented via persisted invocation result path guard.
- Fallback is bounded and never silent.
- Success artifacts cannot be written without `output_reference`.
- Failure conditions map deterministically to terminal states.
- Queue updates are deterministic and fail closed on invalid input.

## Tests
Focused suite added in `tests/test_prompt_queue_live_review_invocation.py` covering:
- codex success path from valid `review_triggered` item
- all allowed fallback reasons
- no fallback when reason is null
- success artifact rejection when output reference is null
- failure mapping to `review_invocation_failed`
- lineage mismatch/missing trigger mapping to `blocked`
- duplicate invocation prevention
- artifact-write failure mapping to `blocked`
- queue update failure retry-then-block behavior
- invocation result schema validation
- deterministic behavior for same input + provider outcome

## Failure modes and remaining gaps
Deferred to future slices:
- review parsing handoff from `output_reference`
- retries and retry scheduling
- blocked-item recovery and operational tooling
- queue scheduling / multi-item orchestration
- provider abstraction expansion beyond codex/claude bounded policy
