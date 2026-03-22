# Architecture Review Action Tracker

- **Source Review:** `docs/reviews/governed_prompt_queue_live_review_invocation_impl_review.md`
- **Review ID:** 2026-03-22-governed-prompt-queue-live-review-invocation-impl-review
- **Owner:** —
- **Last Updated:** 2026-03-22

## Critical Items

| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
|---|---|---|---|---|---|
| LI-CR-1 | Add cross-field constraint: when `fallback_used: true`, `fallback_reason` must be non-null and a member of the bounded enum; when `fallback_used: false`, `fallback_reason` must be null. Enforce at artifact write time (schema `if/then` or pre-write guard). | — | Open | Blocks invocation artifact write | Acceptance: artifact with `fallback_used: true` + `fallback_reason: null` must be rejected before persistence |
| LI-CR-2 | Add enforcement that `output_reference` is non-null when `invocation_status: "success"`. Enforce at artifact write time (schema `if/then` or pre-write guard). Null `output_reference` must be rejected on success paths. | — | Open | Blocks success artifact integrity | Acceptance: success artifact with null output_reference must be rejected; failure artifact may have null |
| LI-CR-3 | Publish explicit invocation write-ordering specification as a named design artifact or documented contract before implementation begins. Required ordering: (1) idempotency guard, (2) trigger lineage validation, (3) transition to `review_invoking`, (4) invoke provider, (5) write artifact, (6) persist `review_invocation_result_artifact_path`, (7) transition to terminal state. | — | Open | Blocks implementation start | Acceptance: ordering is documented in a committed artifact; no deviation without ADR |
| LI-CR-4 | Publish failure-condition-to-terminal-state mapping before implementation begins. Specify: provider fails before output received → `review_invocation_failed`; artifact write fails → `blocked`; queue state update fails → retry then `blocked`; lineage validation fails → `blocked`; schema validation fails → `blocked`. | — | Open | Blocks implementation start | Acceptance: mapping is documented in a committed artifact; implementation references it |
| LI-CR-5 | Formalize minimum invocation precondition checklist as a named step in the entry logic. The five preconditions are: (1) status == `review_triggered` strictly; (2) `review_trigger_artifact_path` is non-null; (3) trigger artifact at that path is readable and its `work_item_id` matches the current work item; (4) trigger artifact's `execution_result_artifact_path` is non-null and readable; (5) `review_invocation_result_artifact_path` is null. Lineage re-validation (3, 4) must re-read from disk. | — | Open | Blocks implementation start | Acceptance: preconditions are explicitly enforced before any state transition; a work item failing any precondition does not advance to `review_invoking` |

## Low-Priority Items

| ID | Action Item | Owner | Status | Blocking Dependencies | Notes |
|---|---|---|---|---|---|
| LI-OD-1 | Add deterministic `invocation_id` field to `prompt_queue_review_invocation_result.schema.json`. Computed as `hash(work_item_id + review_trigger_artifact_path)`. Enables reconciliation of orphaned artifacts and provides a stable audit identifier. | — | Open | — | Optional; strengthens audit without expanding scope |
| LI-OD-2 | Document `auth_failure` as an elevated-scrutiny fallback reason. When `fallback_reason: "auth_failure"`, the invocation result artifact `error_summary` must include a warning string indicating configuration validation is required. | — | Open | — | Optional; provides audit visibility for configuration defects |

## Blocking Items

- **LI-CR-3** (write ordering) and **LI-CR-4** (failure-to-state mapping) must be resolved before implementation begins. These define the behavioral contract for the invocation implementation.
- **LI-CR-1** and **LI-CR-2** must be resolved before the first invocation result artifact is written. These may be schema updates or implementation guards.
- **LI-CR-5** (precondition checklist) must be resolved before implementation begins. Without it, the invocation entry logic is ambiguous.

## Deferred Items

- **D-1** (blocked item recovery path) — defer until `blocked` state accumulates work items or a retry/scheduling slice is designed.
- **D-2** (provider output format contract) — defer until review parsing slice is designed.
- **D-3** (concurrent invocation safety) — defer until queue-wide orchestration is introduced.
- **D-4** (fallback reason enum expansion) — defer; expand only based on observed failure evidence in production.
