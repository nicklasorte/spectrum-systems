# Governed Prompt Queue — Live Review Invocation Implementation Review

## Review Metadata

- **Review Date:** 2026-03-22
- **Review Type:** Pre-implementation surgical design review — first bounded live review invocation slice
- **Repository:** spectrum-systems
- **Reviewer:** Claude (Reasoning Agent — Sonnet 4.6)
- **Review ID:** 2026-03-22-governed-prompt-queue-live-review-invocation-impl-review
- **Reconciles Prior Reviews:**
  - `governed_prompt_queue_live_review_invocation_codex_review` (Codex surgical review, 2026-03-22)
  - `governed_prompt_queue_live_review_invocation_foundation_report` (foundation implementation, 2026-03-22)
- **Inputs Consulted:**
  - `docs/reviews/governed_prompt_queue_live_review_invocation_codex_review.md`
  - `docs/reviews/governed_prompt_queue_live_review_invocation_foundation_report.md`
  - `contracts/schemas/prompt_queue_review_invocation_result.schema.json`
  - `contracts/examples/prompt_queue_review_invocation_result.json`
  - `docs/design-review-standard.md`
  - `docs/review-to-action-standard.md`

---

## Scope

**In scope — this review judges only:**

- Whether `review_triggered` is the correct and sufficient invocation entry state
- Whether the duplicate-invocation prevention design is safe for this MVP
- Whether provider fallback reasons are sufficiently bounded
- Whether the invocation result artifact schema is sufficient for an audit-grade MVP
- Whether partial failure handling is adequately specified
- Whether the minimal four-state path is correct and complete for this slice

**Explicitly out of scope:**

- Review output parsing
- Findings normalization
- Repair prompt generation
- Retry scheduling
- Queue-wide orchestration
- Multi-item execution
- PR or merge automation
- Full provider abstraction redesign
- Long-term agent autonomy

---

## Decision

**PASS**

The foundation slice has closed all four critical findings from the prior Codex surgical review. The proposed MVP is architecturally bounded. The remaining gaps identified below are implementation-specification gaps that must be resolved before live invocation code is written, but they do not require architectural redesign. The system is safe to build against with the required design fixes applied.

---

## Critical Findings (max 5)

### CF-1: Schema permits `fallback_used: true` with `fallback_reason: null` — cross-field invariant missing

**What is wrong:**
`prompt_queue_review_invocation_result.schema.json` defines `fallback_reason` as nullable and `fallback_used` as a boolean, but no cross-field constraint enforces that when `fallback_used == true`, `fallback_reason` must be non-null. The schema is structurally valid when both `fallback_used: true` and `fallback_reason: null` are present simultaneously.

**Why it is dangerous:**
Audit-grade review requires that every fallback be captured explicitly with a bounded reason. An artifact recording `fallback_used: true` with no reason is unauditable — a human reviewer cannot determine whether the fallback was legitimate (e.g., `rate_limited`) or the result of a code defect that silently swallowed the reason. Queue state advance is allowed based on a schema-valid but logically incoherent artifact.

**How it could fail in a real governed queue scenario:**
The implementation invokes Codex, receives an unexpected error type, silently maps it to null, sets `fallback_used: true`, and writes an artifact that passes schema validation. Claude is invoked as fallback. The artifact is accepted, queue advances to `review_invocation_succeeded`, and the audit trail carries no evidence of why the fallback occurred. A future audit cannot determine whether this was a policy-conformant fallback or a defect.

---

### CF-2: `output_reference` is nullable on `invocation_status: success` paths — no schema enforcement

**What is wrong:**
The schema allows `output_reference` to be null regardless of `invocation_status`. On a successful invocation, the output_reference field should point to the produced review artifact. There is no schema-level or implementation-level requirement that `output_reference` be non-null when `invocation_status == "success"`.

**Why it is dangerous:**
The invocation result artifact is the lineage anchor for all downstream steps (review parsing, findings normalization, repair prompt generation). If `output_reference` is null on a success artifact, the downstream consumer — when it exists — has no pointer to the actual review output and cannot proceed. Worse, the artifact itself asserts success while providing no evidence of what was produced, making it audit-incomplete.

**How it could fail in a real governed queue scenario:**
The implementation writes a success artifact but omits `output_reference` due to a path-resolution defect. Schema validation passes. Queue advances to `review_invocation_succeeded`. The work item is in a terminal success state with no pointer to the review output. A subsequent review-parsing slice has a confirmed success artifact but cannot locate what to parse.

---

### CF-3: Safe write ordering is not yet contractually specified in the design

**What is wrong:**
The foundation established the guard primitives (`has_duplicate_review_invocation_result`, `assert_no_duplicate_review_invocation`) and the `review_invocation_result_artifact_path` field. However, the required write ordering for safe partial-failure handling has not been explicitly specified in any design artifact. The correct ordering is:

1. Assert no prior invocation (idempotency guard, using the persisted path field)
2. Validate trigger lineage (confirm trigger artifact work_item_id and upstream paths match)
3. Transition work item to `review_invoking`
4. Invoke provider
5. Write schema-validated invocation result artifact to a deterministic path
6. Update `review_invocation_result_artifact_path` on the work item
7. Transition work item to terminal state (`review_invocation_succeeded` or `review_invocation_failed`)

**Why it is dangerous:**
If an implementor sequences step 7 before step 6, or step 5 after step 7, or skips step 3, the partial failure recovery behavior becomes undefined. Each reordering creates a distinct silent failure mode. Without an explicit ordering specification, the implementation is ambiguous and partial-failure behavior is left to implementor judgment.

**How it could fail in a real governed queue scenario:**
An implementor transitions to `review_invocation_succeeded` before writing the artifact (steps 7 before 5). A crash between those steps leaves the work item in a terminal success state with no artifact and no persisted path. The idempotency guard subsequently finds the path is null, allows re-invocation, and a duplicate provider call occurs — exactly the failure the foundation was designed to prevent.

---

### CF-4: `review_invoking → blocked` fail-closed path must be explicitly required, not just available

**What is wrong:**
The foundation report describes `review_invoking → blocked` as a "fail-closed safety path" and lists it as a legal transition. However, it is not explicitly required — the implementation design does not specify which failure conditions must trigger this path versus which conditions transition to `review_invocation_failed`. These are distinct outcomes: `blocked` signals that a human needs to intervene; `review_invocation_failed` may be treated as a programmatic failure eligible for future retry or automated recovery. Without specifying which conditions map to which terminal state, implementations will differ.

**Why it is dangerous:**
If artifact write fails (step 5 in CF-3's ordering), the work item is in `review_invoking` with a provider call already completed. This is not a normal invocation failure — it is a persistence failure requiring human attention. If the implementation transitions to `review_invocation_failed` instead of `blocked`, a future retry policy might automatically re-invoke the provider against a work item whose provider already returned output, creating a second review invocation with no lineage link to the first.

**How it could fail in a real governed queue scenario:**
Artifact write fails due to storage unavailability. Implementation transitions to `review_invocation_failed`. A future retry scheduler (in a later slice) sees `review_invocation_failed` and re-queues the item for invocation. Provider is called a second time. Both invocations produced output; the first output is orphaned in the provider's storage (if any) with no artifact on disk and no work-item reference. The queue has re-invoked based on a state that should have required human review.

---

### CF-5: Minimum invocation precondition checklist is not formalized — entry validation is under-specified

**What is wrong:**
The foundation established legal state transitions from `review_triggered → review_invoking`, but does not specify the minimum precondition checklist that the invocation entry logic must satisfy before the transition is allowed. The minimum safe preconditions are:

1. Work item status is exactly `review_triggered` (strict equality, not a subset check)
2. `review_trigger_artifact_path` is non-null on the work item
3. The trigger artifact at that path is readable and its embedded `work_item_id` matches the current work item's ID
4. The trigger artifact's `execution_result_artifact_path` is non-null and points to a readable artifact
5. `review_invocation_result_artifact_path` is null on the work item (idempotency guard)

**Why it is dangerous:**
Without a formalized precondition checklist, an implementation may skip lineage re-validation and call the provider with a work item that has a corrupt or mismatched trigger artifact. This produces an invocation result that asserts a lineage chain that is false, advancing the queue state based on a review that was invoked against the wrong trigger context.

**How it could fail in a real governed queue scenario:**
A work item is rehydrated from disk with a stale `review_trigger_artifact_path` from a previous run. The implementation checks only that status is `review_triggered` and that the path field is non-null. It invokes the provider without re-reading the trigger artifact. The resulting invocation result artifact records the stale trigger path as authoritative lineage. The review is based on execution results from a different work item context.

---

## Required Design Fixes

### RDF-1: Add cross-field constraint for fallback_reason when fallback_used is true

Add schema-level or implementation-level enforcement:
- When `fallback_used: true`, `fallback_reason` must be a non-null member of the bounded enum
- When `fallback_used: false`, `fallback_reason` must be null
- Enforce this at artifact write time, before schema validation is considered passed

Preferred approach: add a JSON Schema `if/then` block or enforce in the artifact writer before persisting. Either is acceptable for MVP; implementation enforcement is the minimum.

### RDF-2: Enforce non-null `output_reference` on success invocations

Add validation at artifact write time:
- If `invocation_status: "success"`, `output_reference` must be non-null and must point to a readable file path
- If `invocation_status: "failure"`, `output_reference` may be null

This may be implemented as schema-level enforcement (`if/then`) or as a pre-write guard in the artifact writer. The schema update is preferred for long-term audit integrity.

### RDF-3: Publish an explicit invocation write-ordering specification

Before implementation begins, specify the required write ordering as a named design artifact or as a documented contract in the invocation logic module. The ordering must be:

1. Assert no prior invocation (idempotency guard)
2. Validate trigger lineage (read and verify trigger artifact)
3. Transition to `review_invoking`
4. Invoke provider
5. Write schema-validated invocation result artifact to deterministic path
6. Persist `review_invocation_result_artifact_path` on work item
7. Transition to terminal state

Implementors must not deviate from this ordering without a documented architectural decision.

### RDF-4: Explicitly specify which failure conditions require `blocked` vs `review_invocation_failed`

Publish a mapping before implementation begins:

| Failure Condition | Required Terminal State |
|---|---|
| Provider invocation fails (any bounded reason, before output received) | `review_invocation_failed` |
| Provider returns; artifact write fails | `blocked` |
| Artifact write succeeds; queue state update fails | Retry state update; if unable, `blocked` |
| Trigger lineage validation fails at precondition check | `blocked` |
| Schema validation of result artifact fails | `blocked` |

The `blocked` state is the fail-closed fallback when the failure mode implies human review is required before any automated recovery.

### RDF-5: Formalize the minimum invocation precondition checklist

Document the five preconditions listed in CF-5 as a named step in the invocation entry logic. The entry validation must run before any state transition occurs. Lineage re-validation (preconditions 3 and 4) must re-read the trigger artifact from disk, not from in-memory state.

---

## Optional Design Improvements

### ODI-1: Add a deterministic `invocation_id` field to the result artifact

As suggested by the prior Codex review: compute `invocation_id = hash(work_item_id + review_trigger_artifact_path)` and embed it in the invocation result artifact. This enables reconciliation of orphaned artifacts when `review_invocation_result_artifact_path` is null but the artifact exists on disk, and provides a stable audit identifier independent of file paths.

This does not expand scope — it strengthens artifact traceability without adding new behaviors.

### ODI-2: Document `auth_failure` as an elevated-scrutiny fallback reason

`auth_failure` is included in the bounded fallback reason enum and is therefore a legal fallback trigger. However, auth failures almost always indicate configuration defects, not transient provider conditions. Falling back to Claude on an auth failure hides a likely misconfiguration behind a legitimate-looking audit trail.

Require that when `fallback_reason: "auth_failure"`, the invocation result artifact records an elevated warning in `error_summary` (e.g., `"auth_failure: configuration validation required"`). This provides a visible signal in the audit trail without removing the reason from the enum or blocking the fallback behavior.

---

## Trust Assessment

**YES**

The foundation has closed all four blocking critical findings from the Codex surgical review:
- Provider policy is now Codex-first (corrected in foundation)
- Legal invocation state path from `review_triggered` now exists (corrected in foundation)
- Invocation result artifact schema is now defined (corrected in foundation)
- `review_invocation_result_artifact_path` idempotency field now exists on work items (corrected in foundation)

The five critical findings in this review are implementation-specification gaps — the design has not yet fully specified the write ordering, the cross-field invariants, and the failure-condition-to-state mapping. These gaps must be closed before implementation begins, but they do not require redesigning the foundation.

The design is fail-closed at the architectural level: `review_invoking → blocked` exists as a safe escape valve, and the idempotency guard is structurally present. With RDF-1 through RDF-5 applied, this first bounded live review invocation implementation can be built safely.

---

## Failure Mode Summary

**Worst realistic failure if implemented naively:**

The implementation invokes Codex, receives an unexpected failure type not mapped in the fallback reason enum. The code silently maps it to null and falls back to Claude. Claude returns a review. The implementation writes the artifact before setting `review_invocation_result_artifact_path`, then crashes. On restart: the artifact exists on disk but the work item path field is null. The idempotency guard finds no persisted path, allows re-invocation, and Claude is called a second time. Two conflicting review artifacts now exist for one trigger. Both are schema-valid. The queue has no mechanism to detect which artifact to use. Both artifacts record `fallback_reason: null`, providing no audit evidence that the Codex call was even attempted. The lineage chain from execution result → review trigger → review invocation is broken.

This failure is prevented by the combination of RDF-1 (cross-field invariant), RDF-3 (write ordering: set path before transitioning), and RDF-4 (failed artifact write → `blocked`, not re-invocable).

---

## Recommended MVP Boundary

### Include in the first live review invocation implementation prompt:

1. Invocation entry precondition checklist (RDF-5): status check, trigger artifact readability and lineage match, null idempotency guard
2. State transition to `review_invoking` before any provider call
3. Codex-first provider invocation with bounded fallback to Claude only for: `usage_limit`, `rate_limited`, `auth_failure`, `timeout`, `provider_unavailable`
4. Cross-field enforcement: `fallback_used: true` requires non-null `fallback_reason` (RDF-1)
5. Schema-validated invocation result artifact write with non-null `output_reference` on success (RDF-2)
6. Explicit write ordering as specified in RDF-3 (steps 1–7)
7. Explicit failure-to-state mapping as specified in RDF-4
8. Terminal state transition to `review_invocation_succeeded` or `review_invocation_failed` or `blocked` per the mapping

### Explicitly defer until later:

- Review output parsing (the artifact `output_reference` field is the handoff point; parsing is the next slice)
- Findings normalization
- Repair prompt generation
- Retry or scheduling logic (RDF-4 defines `blocked` as the floor — manual or scheduled recovery is a future slice)
- Multi-item orchestration
- Provider abstraction redesign
- Any merge or PR automation

---

## Deferred Concerns

These are broader concerns outside the scope of this MVP judgment. They are recorded for future review planning only.

**D-1: Recovery path for items stuck in `review_invoking`**
When artifact write fails and the item transitions to `blocked`, a future slice must define how a human or sweep process advances `blocked` items back through the queue. This is not needed for the first invocation slice, but the `blocked` terminal state will accumulate work items without a recovery mechanism.

**D-2: Provider output format contract**
The `output_reference` field points to the review output file, but no contract specifies what format Codex or Claude output must be in at that path. This is fine for MVP (parsing is deferred), but the absence of an output format contract will create an ambiguous handoff when the parsing slice is implemented.

**D-3: Concurrent invocation safety**
This MVP is scoped to a single `review_triggered` item at a time. When queue-wide orchestration is introduced, the `review_invoking` state provides the primary concurrency guard, but the idempotency guard pattern assumes single-writer semantics. Concurrent writer scenarios are out of scope but will require re-evaluation.

**D-4: Bounded fallback reason enum expansion**
The current enum covers the most common transient failure types. Edge cases (network errors, malformed API responses, quota reset timing) may not map cleanly to existing reasons. Enum expansion should be gated on observed failure evidence, not pre-emptive speculation.

---

## Extracted Action Items

| ID | Action Item | Priority | Owner | Status | Blocking Dependency |
|---|---|---|---|---|---|
| LI-CR-1 | Add cross-field constraint: fallback_used=true requires non-null fallback_reason (RDF-1) | Critical | — | Open | Blocks invocation artifact write |
| LI-CR-2 | Add enforcement: output_reference must be non-null when invocation_status=success (RDF-2) | Critical | — | Open | Blocks success artifact integrity |
| LI-CR-3 | Publish explicit invocation write-ordering specification (RDF-3) | Critical | — | Open | Blocks implementation start |
| LI-CR-4 | Publish failure-condition-to-state mapping (blocked vs invocation_failed) (RDF-4) | Critical | — | Open | Blocks implementation start |
| LI-CR-5 | Formalize minimum invocation precondition checklist (RDF-5) | Critical | — | Open | Blocks implementation start |
| LI-OD-1 | Add deterministic invocation_id field to result artifact schema (ODI-1) | Low | — | Open | — |
| LI-OD-2 | Document auth_failure as elevated-scrutiny reason in implementation notes (ODI-2) | Low | — | Open | — |

## Blocking Items

- LI-CR-3 and LI-CR-4 must be resolved before implementation begins. Without an explicit write ordering and a failure-to-state mapping, the implementation cannot be written safely.
- LI-CR-1 and LI-CR-2 must be resolved before the first invocation result artifact is written. These may be addressed as implementation guards or schema updates; either is acceptable.

## Deferred Items

- D-1 (blocked item recovery) — defer until `blocked` state accumulates work items or a retry/scheduling slice is designed.
- D-2 (provider output format contract) — defer until review parsing slice is designed.
- D-3 (concurrent invocation safety) — defer until queue-wide orchestration is introduced.
- D-4 (fallback reason enum expansion) — defer; expand only based on observed failure evidence.
