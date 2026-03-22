# Governed Prompt Queue — Controlled Execution MVP Design Review

**Date:** 2026-03-22
**Reviewer:** Claude (reasoning agent)
**Branch:** `claude/review-execution-mvp-JEMmq`
**Inputs consulted:**
- `docs/reviews/governed_prompt_queue_execution_gating_report.md`
- `docs/reviews/governed_prompt_queue_repair_child_creation_report.md`
- `docs/reviews/governed_prompt_queue_mvp_report.md`
- `docs/reviews/governed_prompt_queue_repair_prompt_report.md`
- `spectrum_systems/modules/prompt_queue/queue_state_machine.py`
- `spectrum_systems/modules/prompt_queue/queue_models.py`
- `spectrum_systems/modules/prompt_queue/execution_gating_policy.py`
- `contracts/schemas/prompt_queue_work_item.schema.json`
- `contracts/schemas/prompt_queue_execution_gating_decision.schema.json`

---

## Scope

**In scope:** The first bounded controlled-execution MVP only:
- Selecting a single work item already in `runnable` state
- Performing a bounded simulated (non-live) execution
- Emitting a schema-backed execution result artifact
- Updating queue and work-item state deterministically
- Preserving lineage from: review → findings → repair prompt → child work item → gating decision → execution result
- Blocking duplicate execution of the same runnable work item

**Out of scope (not evaluated):**
- Retries, rollback semantics
- Queue scheduling, prioritization, parallelism
- Provider orchestration, live Codex/Claude execution
- Merge/close automation, approval UX
- Multi-item coordination, long-term execution policy

---

## Decision

**PASS — with required fixes before implementation begins**

The conceptual intent of the MVP is sound and appropriately bounded. The existing gating infrastructure provides a well-structured precondition chain. However, four concrete design gaps make the naive implementation unsafe. All four are fixable within the MVP boundary without expanding scope.

---

## Critical Findings

### CF-1: `RUNNABLE` is a terminal state — no execution path exists

**What is wrong:** In `queue_state_machine.py`, `WorkItemStatus.RUNNABLE.value` maps to `set()` — an empty transition set. No transition out of `runnable` is defined.

**Why it is dangerous:** There is literally no safe path from `runnable` to any post-execution state. Any implementation attempt would require patching the state machine mid-execution, which is exactly the kind of ad-hoc mutation that produces inconsistent states.

**How it fails:** A work item reaches `runnable` through the full gating chain. The executor tries to move it to an outcome state. The state machine raises `IllegalTransitionError`. The execution loop either: (a) bypasses the state machine (breaking the invariant the entire queue is built on), or (b) crashes with an unhandled error, leaving the item stuck at `runnable` forever.

**Required fix:** Add `executing`, `executed_success`, and `executed_failure` to `WorkItemStatus` and to `_ALLOWED_TRANSITIONS` before any implementation of the execution slice begins.

---

### CF-2: No intermediate `executing` state — duplicate execution is unpreventable

**What is wrong:** The design moves directly from `runnable` to the execution result write, then to a terminal outcome state. There is no intermediate state to mark that execution is in progress.

**Why it is dangerous:** If a process is interrupted after the execution result artifact is written but before the queue state update completes, the work item remains at `runnable`. On restart or retry, nothing prevents a second execution attempt — the only guard is the work-item status field, which was never updated.

**How it fails:** Simulated execution completes. Result artifact written to disk. Process crashes. Queue state still shows `runnable`. Operator re-invokes the executor. A second result artifact is emitted for the same work item with a different `execution_result_artifact_id`. The queue now has two conflicting execution records with no reconciliation path.

**Required fix:** Transition `runnable -> executing` as the first step — before any execution begins. This is the atomic guard. Once a work item is `executing`, a duplicate invocation will see the status and halt. See CF-4 for how the result artifact provides the second layer of protection if state update also fails.

---

### CF-3: No execution result artifact schema exists

**What is wrong:** The proposed MVP requires emitting a "schema-backed execution result artifact," but no such schema is defined anywhere in the contracts directory.

**Why it is dangerous:** Without a schema, the execution result has no validated structure, no enforced lineage fields, no durable identity, and no audit-grade guarantees. The gating decision artifact only proves a `runnable` decision was made — it does not prove execution happened or what the outcome was. The execution result is the only artifact that closes this audit gap.

**How it fails:** The executor emits an unvalidated JSON blob. Contract enforcement (`run_contract_enforcement.py`) does not know the schema exists. Future repair loops, dashboards, or audits cannot reliably read execution outcomes. The lineage chain from review → execution result is broken.

**Required fix:** Define `contracts/schemas/prompt_queue_execution_result.schema.json` (minimum required fields specified in "Required Design Fixes" below) before implementation begins.

---

### CF-4: Gating decision artifact is not re-validated at execution time

**What is wrong:** The proposed MVP trusts the work-item `status == "runnable"` field as the sole precondition for execution. The `gating_decision_artifact_path` on the work item is not re-read and re-validated at the point of execution.

**Why it is dangerous:** The work-item status field is mutable state. A gating decision artifact is an immutable, schema-backed record. If the status field were ever incorrectly set (manual correction, migration error, test harness leak), the work item could reach `executing` without a valid gating decision artifact on disk.

**How it fails:** A work item's status is manually patched to `runnable` during debugging. No gating decision artifact exists or the artifact on disk carries `decision_status == "blocked"`. The executor does not re-read the artifact. Execution proceeds against a work item that was never cleared by the gating policy.

**Required fix:** At execution entry, load and re-validate the referenced `gating_decision_artifact_path`. Confirm `decision_status == "runnable"`. Fail closed and transition to `blocked` if the artifact is missing, schema-invalid, or carries any status other than `runnable`.

---

## Required Design Fixes

### RDF-1: Extend the state machine with execution states

Add to `WorkItemStatus`:
```
EXECUTING = "executing"
EXECUTED_SUCCESS = "executed_success"
EXECUTED_FAILURE = "executed_failure"
```

Add to `_ALLOWED_TRANSITIONS`:
```
RUNNABLE -> {EXECUTING}
EXECUTING -> {EXECUTED_SUCCESS, EXECUTED_FAILURE, BLOCKED}
```

Note: `BLOCKED` as an escape from `EXECUTING` handles the case where execution is interrupted and manually triaged.

### RDF-2: Define the execution result artifact schema

Minimum required fields for `contracts/schemas/prompt_queue_execution_result.schema.json`:

| Field | Type | Notes |
|---|---|---|
| `execution_result_artifact_id` | string | unique, non-null |
| `work_item_id` | string | non-null |
| `parent_work_item_id` | string \| null | lineage |
| `repair_prompt_artifact_path` | string \| null | lineage |
| `gating_decision_artifact_path` | string \| null | lineage |
| `spawned_from_findings_artifact_path` | string \| null | lineage |
| `spawned_from_review_artifact_path` | string \| null | lineage |
| `execution_mode` | string (const `"simulated"`) | for this MVP |
| `execution_status` | string enum `["success", "failure"]` | |
| `started_at` | date-time | |
| `completed_at` | date-time | |
| `output_reference` | string \| null | path or null |
| `error_summary` | string \| null | null on success |
| `generated_at` | date-time | |
| `generator_version` | string | |

The artifact must be schema-validated before write. If validation fails, execution is not recorded as complete, and the work item must transition to `executed_failure` or `blocked`.

### RDF-3: Execution entry must re-validate the gating decision artifact

Before transitioning to `executing`, the executor must:
1. Load the artifact at `work_item["gating_decision_artifact_path"]`
2. Schema-validate it against `prompt_queue_execution_gating_decision.schema.json`
3. Confirm `decision_status == "runnable"`

If any of these checks fail, halt and transition the work item to `blocked`. Do not proceed to `executing`.

### RDF-4: Define partial failure handling explicitly

The safe ordering for the MVP execution sequence is:
1. Re-validate gating decision artifact (CF-4)
2. Transition work item: `runnable -> executing` and persist queue state
3. Run simulated execution
4. Write execution result artifact (schema-validated)
5. Transition work item: `executing -> executed_success | executed_failure` and persist queue state

If step 4 fails: transition to `executed_failure` via step 5. No result artifact means failure.

If step 5 fails after step 4 succeeds: the work item is stuck in `executing`. On any subsequent run, the executor must detect `executing` status and check whether a result artifact already exists on disk. If found and valid, complete the state transition. If not found, transition to `executed_failure`. This behavior must be documented, even if not implemented in the first slice.

---

## Optional Design Improvements

### ODI-1: Add `execution_attempt_id` to the result artifact

A random UUID in the execution result artifact enables idempotency comparison in future replay or retry scenarios without expanding current scope. Cost is one additional field.

### ODI-2: Record `source_queue_state_path` in the execution result artifact

Mirrors the pattern already established in the gating decision schema. Allows the execution result artifact to be traced back to the queue snapshot that authorized it. Adds one nullable field.

### ODI-3: Add a duplicate-execution check keyed on `work_item_id` in the result artifact directory

Before transitioning to `executing`, scan the result artifact output directory for any existing execution result artifact whose `work_item_id` matches. If found and valid, refuse execution and log. This provides a second layer of duplicate protection independent of the state machine — important if the state is ever inconsistent.

---

## Trust Assessment

**YES** — this first bounded controlled-execution MVP can be implemented safely with fail-closed behavior, provided the four required design fixes are applied before implementation begins.

The existing gating infrastructure is well-constructed. The lineage chain is complete. The state machine enforces legal transitions. The only gaps are: missing terminal states, missing `executing` guard, missing result artifact schema, and missing gating re-validation at execution entry. All four are mechanical additions within the existing design pattern.

---

## Failure Mode Summary

**Worst realistic failure if implemented naively (without required fixes):**

A work item passes gating and reaches `runnable`. The executor runs simulated execution and writes a result artifact. Before the queue state update completes, the process is interrupted (timeout, OOM, keyboard interrupt). The work item remains at `runnable` — because there is no `executing` guard, and no result artifact check at entry. A second operator invocation sees `runnable`, passes all entry checks (status is valid, gating artifact exists and says `runnable`), and runs a second execution. Two result artifacts are emitted for the same work item with different `execution_result_artifact_id` values and potentially different `execution_status` outcomes. The queue is now in an irreconcilable state: one `success` and one `failure` both attributed to the same work item, with no authoritative record of which should be trusted. The repair loop has no safe continuation.

---

## Recommended MVP Boundary

### Include in the first controlled-execution implementation:

- Add `executing`, `executed_success`, `executed_failure` to `WorkItemStatus` and `_ALLOWED_TRANSITIONS`
- Define `contracts/schemas/prompt_queue_execution_result.schema.json` with minimum required fields above
- An execution entry check: re-read and re-validate the gating decision artifact; fail closed if not `runnable`
- A thin simulated execution adapter (no live provider calls, deterministic output)
- Execution result artifact construction and schema validation before write
- Deterministic queue/work-item state updates: `runnable -> executing -> executed_success | executed_failure`
- Duplicate prevention: refuse execution if work-item status is not exactly `runnable` at entry
- A CLI script (`scripts/run_prompt_queue_execution.py`) scoped to single-item execution only
- Tests covering: success path, failure path, duplicate guard, missing gating artifact, invalid gating artifact, partial failure (result written but state update fails), schema validation of result artifact

### Explicitly defer:

- Live Codex/Claude execution dispatch
- Retry logic and backoff
- Rollback semantics
- Queue-wide item selection or prioritization
- Parallel or concurrent execution
- Merge/close automation
- Approval UX beyond explicit flag input
- Multi-item coordination
- Long-term execution policy generalization

---

## Deferred Concerns

The following broader concerns are out of scope for this MVP judgment and are noted only for future roadmap awareness:

- **Retry semantics:** Once `executed_failure` exists as a terminal state, future slices will need to define whether failed items can be re-queued, and under what conditions. The generation counter and `max_generation_allowed` policy already provide the structural basis.
- **Queue-wide execution scheduling:** The current queue model has a single `active_work_item_id`. Future multi-item execution will require a scheduler that selects from `runnable` items. This is entirely deferred.
- **Live provider execution:** The simulated adapter is a deliberate boundary. Actual Codex/Claude execution introduces latency, failure modes, and output variability that are out of scope for this MVP.
- **Execution result observability:** The execution result artifact provides per-item audit evidence, but queue-level execution dashboards and SLO tracking are future concerns.
