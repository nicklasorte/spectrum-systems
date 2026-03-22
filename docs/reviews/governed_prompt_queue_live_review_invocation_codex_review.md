# Governed Prompt Queue Live Review Invocation MVP — Codex Surgical Review

Date: 2026-03-22

## Scope reviewed
- Requested design artifact path: `docs/reviews/governed_prompt_queue_live_review_invocation_mvp_review.md` (not present in repository at review time).
- Adjacent prompt-queue invocation and state surfaces only:
  - `spectrum_systems/modules/prompt_queue/review_provider_orchestrator.py`
  - `spectrum_systems/modules/prompt_queue/queue_models.py`
  - `spectrum_systems/modules/prompt_queue/queue_state_machine.py`
  - `spectrum_systems/modules/prompt_queue/review_trigger_policy.py`
  - `spectrum_systems/modules/prompt_queue/review_trigger_queue_integration.py`
  - `contracts/schemas/prompt_queue_work_item.schema.json`
  - `contracts/schemas/prompt_queue_review_attempt.schema.json`
  - `contracts/schemas/prompt_queue_review_trigger.schema.json`
  - `scripts/run_prompt_queue.py`
  - `tests/test_prompt_queue_mvp.py`

## Decision
FAIL

## Critical Findings (max 5)

1) **Wrong provider path is currently hard-wired opposite to MVP policy**
- **What is wrong:** Current queue model and orchestrator enforce primary `claude` with fallback to `codex`, not primary `codex` with fallback `claude`.
- **Why dangerous:** The first live invocation slice can route review invocations through the wrong provider by default, violating policy and audit expectations before any runtime fallback logic is even evaluated.
- **Location:** `review_provider_primary` default is `claude` in `queue_models.py`; schema const also pins it to `claude`; orchestrator calls `run_claude` first and `run_codex` second.
- **Failure scenario:** A `review_triggered` item is invoked in production and always starts on Claude even when policy requires Codex-first, causing policy non-conformance and potentially different review outcomes.

2) **No bounded live-invocation handoff from `review_triggered` into invocation states**
- **What is wrong:** State machine makes `review_triggered` terminal (`set()` outgoing transitions), while invocation orchestrator expects transitions `queued -> review_queued -> review_running`; there is no legal transition path linking triggered review work to invocation execution.
- **Why dangerous:** Teams may bypass or patch around state validation ad hoc to make invocation run, creating silent fallthroughs and unsafe advancement.
- **Location:** `queue_state_machine.py` (`REVIEW_TRIGGERED: set()`), `review_provider_orchestrator.py` (immediate transition attempts to `review_queued` then `review_running`).
- **Failure scenario:** Operator invokes review runner on a `review_triggered` item; it fails transition checks, then an emergency manual status rewrite moves item directly to running/complete without lineage guardrails.

3) **Duplicate invocation guard is insufficient for live invocation stage**
- **What is wrong:** Existing duplicate protection is for trigger-to-child spawn only (`review_trigger_artifact_path`/child ID checks). There is no invocation-result artifact pointer or idempotency key on work item to prove "this trigger has already been invoked".
- **Why dangerous:** Re-running invocation after partial failure can produce duplicate provider calls and conflicting review artifacts while appearing as normal retries.
- **Location:** `review_trigger_queue_integration.py` duplicate checks only before child spawn; `prompt_queue_work_item.schema.json` has no `review_invocation_result_artifact_path` (or equivalent) required field.
- **Failure scenario:** Invocation writes a review artifact but crashes before queue update; rerun re-invokes provider again because no persisted invocation guard binds trigger lineage to a single invocation result.

4) **Invocation artifact minimum is not contract-defined, enabling unsafe loop advancement**
- **What is wrong:** No schema exists for a live review invocation result artifact carrying required lineage and provider decision evidence.
- **Why dangerous:** Queue may advance to `review_complete` based on in-memory result without durable, auditable proof of trigger lineage, provider path taken, fallback reason, and invocation outcome.
- **Location:** `contracts/schemas/` lacks a `prompt_queue_review_invocation_result` contract; `prompt_queue_review_attempt.schema.json` tracks attempts but is not linked in work-item lineage as a required artifact path.
- **Failure scenario:** System marks review complete, then artifact store inconsistencies are discovered later with no canonical invocation result to reconstruct whether fallback was legitimate or duplicate invocation occurred.

## Required Fixes
- Flip provider policy for this slice to **primary `codex`, fallback `claude`** in both model defaults and schema constraints; update orchestrator call order to Codex-first and Claude fallback only on bounded reasons.
- Add one minimal invocation entry state for this slice (e.g., `review_invoking`) and allow only safe transitions:
  - `review_triggered -> review_invoking -> review_complete|review_provider_failed|blocked`
  - keep all other unrelated transitions unchanged.
- Add a minimal invocation-result artifact contract and a required work-item path field (e.g., `review_invocation_result_artifact_path`) used as idempotency guard:
  - if present and lineage matches current trigger, invocation must not run again.
- Enforce invocation preconditions before provider call:
  - valid `review_trigger_artifact_path` exists,
  - trigger artifact `work_item_id` + `parent_work_item_id` + upstream artifact paths match current work item lineage.
- Enforce write ordering for safety:
  - write validated invocation-result artifact first,
  - then atomically/transactionally update queue state to terminal invocation status,
  - fail closed (`blocked`) if state update cannot be committed.

## Optional Improvements
- Keep fallback reason enum bounded as-is, but explicitly reject null/unknown fallback reasons in fallback branch to make audit traces tighter.
- Add a deterministic invocation id (`invocation_id = hash(work_item_id + review_trigger_artifact_path)`) inside invocation-result artifact for easier reconciliation.

## Trust Assessment
NO.

As currently designed/implemented in adjacent patterns, this MVP slice cannot yet be trusted to avoid wrong-provider invocation (policy inversion), duplicate invocation (no invocation-result idempotency artifact), or unsafe loop advancement (no legal `review_triggered` invocation path plus missing invocation-result contract).

## Failure Mode Summary
Worst realistic failure: a `review_triggered` work item is force-advanced into invocation outside legal state transitions, invokes the wrong provider first (Claude), partially writes outputs, and is retried without an invocation guard—creating two conflicting review invocations for one trigger while queue state appears progressed. This yields non-auditable lineage and potentially incorrect downstream repair actions.
