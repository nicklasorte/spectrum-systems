# Governed Prompt Queue Execution Gating Report

**Date:** 2026-03-22

## Scope
Implemented the governed prompt queue execution-gating slice for repair-child work items. This delivery adds deterministic policy evaluation, schema-backed gating decision artifacts, and queue/work-item state integration that fail closed when lineage, approvals, or required inputs are missing.

## Files created/changed
- `contracts/schemas/prompt_queue_execution_gating_decision.schema.json`
- `contracts/examples/prompt_queue_execution_gating_decision.json`
- `contracts/schemas/prompt_queue_work_item.schema.json`
- `contracts/schemas/prompt_queue_state.schema.json`
- `contracts/examples/prompt_queue_work_item.json`
- `contracts/examples/prompt_queue_state.json`
- `contracts/standards-manifest.json`
- `spectrum_systems/modules/prompt_queue/execution_gating_artifact_io.py`
- `spectrum_systems/modules/prompt_queue/execution_gating_policy.py`
- `spectrum_systems/modules/prompt_queue/execution_gating_queue_integration.py`
- `spectrum_systems/modules/prompt_queue/queue_models.py`
- `spectrum_systems/modules/prompt_queue/queue_state_machine.py`
- `spectrum_systems/modules/prompt_queue/__init__.py`
- `scripts/run_prompt_queue_execution_gating.py`
- `tests/test_prompt_queue_execution_gating.py`

## Gating policy summary
- Policy entrypoint: `evaluate_execution_gating_policy(...)` in `execution_gating_policy.py`.
- Deterministic baseline policy:
  - max repair generation default = 2
  - high/critical risk require explicit approval
  - low/medium risk may become runnable if lineage and artifacts are valid and generation limit is respected
  - missing required fields/artifacts/lineage blocks fail-closed
  - malformed work item or repair prompt blocks fail-closed
- Decision statuses emitted:
  - `runnable`
  - `approval_required`
  - `blocked`
- Every decision is emitted as a schema-valid `prompt_queue_execution_gating_decision` artifact with reason code, policy metadata, lineage summary, and blocking conditions.

## State-machine changes
Minimal status expansion added to `prompt_queue_work_item` lifecycle:
- `execution_gated`
- `runnable`
- `approval_required`

Transition updates:
- `repair_child_created -> execution_gated | blocked`
- `execution_gated -> runnable | approval_required | blocked`
- `approval_required -> runnable | blocked`

No execution orchestration was added in this slice.

## Test evidence
Executed:
- `pytest -q tests/test_prompt_queue_execution_gating.py`
- `pytest -q tests/test_prompt_queue_repair_child_creation.py tests/test_prompt_queue_repair_prompt_generation.py tests/test_prompt_queue_mvp.py`
- `pytest -q tests/test_contracts.py tests/test_contract_enforcement.py`
- `python scripts/run_contract_enforcement.py`

New coverage in `tests/test_prompt_queue_execution_gating.py` validates:
- low-risk child within generation limit -> runnable
- high-risk child without approval -> approval_required
- high-risk child with approval -> runnable
- generation limit exceeded -> blocked
- missing lineage -> blocked
- malformed work item -> blocked
- decision artifact validates against schema
- queue/work-item update after decision is deterministic and links artifact path
- illegal/inconsistent state transitions fail closed

## Remaining gaps
Out of scope and deferred:
- automatic execution dispatch for runnable items
- retry policies and scheduling
- queue prioritization and parallelism
- approval UX/workflow beyond explicit input flags
- generalized policy-engine framework
