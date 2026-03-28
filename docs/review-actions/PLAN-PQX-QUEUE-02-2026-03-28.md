# Plan — PQX-QUEUE-02 — 2026-03-28

## Prompt type
PLAN

## Roadmap item
[ROW: QUEUE-02] Step Execution Adapter Normalization

## Objective
Introduce a single deterministic adapter surface for per-step queue execution that validates inputs/outputs fail-closed, reuses existing execution/review seams, and emits schema-valid normalized execution artifacts.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PQX-QUEUE-02-2026-03-28.md | CREATE | Required PLAN artifact before multi-file BUILD work. |
| PLANS.md | MODIFY | Register active PQX-QUEUE-02 plan. |
| spectrum_systems/modules/prompt_queue/execution_runner.py | MODIFY | Add normalized step execution adapter entrypoint that validates/normalizes requests and reuses existing seams. |
| spectrum_systems/modules/prompt_queue/execution_queue_integration.py | MODIFY | Add queue-state integration helper that routes step execution through normalized adapter path without queue advancement logic. |
| spectrum_systems/modules/prompt_queue/execution_artifact_io.py | MODIFY | Harden deterministic execution artifact read/write and fail-closed validation. |
| spectrum_systems/modules/prompt_queue/review_invocation_runner.py | MODIFY | Add normalized review invocation adapter wrapper compatible with queue step adapter surface. |
| spectrum_systems/modules/prompt_queue/review_invocation_provider_adapter.py | MODIFY | Add fail-closed provider result normalization to keep invocation outcomes schema-safe. |
| spectrum_systems/modules/prompt_queue/__init__.py | MODIFY | Export new normalized adapter functions. |
| scripts/run_prompt_queue_execution.py | MODIFY | Keep CLI thin while calling normalized execution adapter and deterministic artifact writer. |
| scripts/run_prompt_queue_live_review_invocation.py | MODIFY | Keep CLI on normalized invocation adapter boundary. |
| contracts/schemas/prompt_queue_execution_result.schema.json | MODIFY | Minimal additive schema extension for normalized execution adapter fields. |
| contracts/examples/prompt_queue_execution_result.json | MODIFY | Keep golden-path example schema-valid with normalized fields. |
| contracts/standards-manifest.json | MODIFY | Version bump and contract metadata update for schema change. |
| tests/test_prompt_queue_execution_runner.py | CREATE | Validate normalized execution adapter fail-closed and deterministic behavior. |
| tests/test_prompt_queue_execution_integration.py | CREATE | Validate queue integration path uses normalized adapter boundary and deterministic refs. |
| tests/test_prompt_queue_live_review_invocation.py | MODIFY | Add assertions that review invocation executes within normalized adapter boundary. |

## Contracts touched
- `prompt_queue_execution_result` (updated, additive)

## Tests that must pass after execution
1. `pytest tests/test_prompt_queue_execution_runner.py`
2. `pytest tests/test_prompt_queue_execution_integration.py`
3. `pytest tests/test_prompt_queue_live_review_invocation.py`
4. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not add transition policy, next-step selection, retry policy, or queue loop execution logic.
- Do not redesign provider execution semantics beyond adapter-surface normalization.
- Do not refactor unrelated prompt queue modules.

## Dependencies
- [ROW: QUEUE-01] Queue Manifest and State Contract Spine must remain authoritative for queue state fields.
