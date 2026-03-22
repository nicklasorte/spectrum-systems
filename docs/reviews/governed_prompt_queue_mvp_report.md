# Governed Prompt Queue MVP Implementation Report

## Date
2026-03-22

## Scope
This delivery implements the orchestration backbone MVP for a governed prompt queue inside `spectrum-systems`: schema-backed queue/work-item/review-attempt artifacts, deterministic lifecycle transitions, provider policy with Claude→Codex fallback, schema-validated artifact emission, and a thin CLI for queue+review simulation.

## Files created/changed
- `contracts/schemas/prompt_queue_work_item.schema.json`
- `contracts/schemas/prompt_queue_state.schema.json`
- `contracts/schemas/prompt_queue_review_attempt.schema.json`
- `contracts/examples/prompt_queue_work_item.json`
- `contracts/examples/prompt_queue_state.json`
- `contracts/examples/prompt_queue_review_attempt.json`
- `contracts/standards-manifest.json`
- `spectrum_systems/modules/prompt_queue/__init__.py`
- `spectrum_systems/modules/prompt_queue/queue_models.py`
- `spectrum_systems/modules/prompt_queue/queue_state_machine.py`
- `spectrum_systems/modules/prompt_queue/review_provider_orchestrator.py`
- `spectrum_systems/modules/prompt_queue/queue_artifact_io.py`
- `scripts/run_prompt_queue.py`
- `tests/test_prompt_queue_mvp.py`
- `docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-MVP-2026-03-22.md`
- `PLANS.md`

## State machine summary
Work item lifecycle statuses:
- `queued`
- `review_queued`
- `review_running`
- `review_provider_failed`
- `review_fallback_running`
- `review_complete`
- `blocked`

The state machine enforces a deterministic allow-list of legal transitions. Any transition outside that map raises an `IllegalTransitionError` and fails closed.

## Provider fallback summary
- Primary provider is Claude.
- Fallback provider is Codex.
- Claude failures with bounded reasons (`usage_limit`, `rate_limited`, `auth_failure`, `timeout`, `provider_unavailable`) trigger fallback.
- Fallback metadata (`review_fallback_used`, `review_fallback_reason`, `review_provider_actual`) is always recorded.
- If Codex also fails, the work item is moved to `blocked`.
- Review attempts are emitted for every provider call; provider failure is never hidden.

## Test evidence
Executed validation/tests:
- `pytest -q tests/test_prompt_queue_mvp.py`
- `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
- `python scripts/run_contract_enforcement.py`

All passed in this implementation pass.

## Remaining gaps
Not included in this MVP (explicitly deferred):
- live provider integrations (Claude/Codex APIs)
- review artifact parsing
- repair loop generation
- dependency scheduling
- queue parallelism
- merge/build/review/repair end-to-end automation
