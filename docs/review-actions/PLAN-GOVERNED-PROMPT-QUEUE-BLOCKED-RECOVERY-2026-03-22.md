# Plan — Governed Prompt Queue Blocked Recovery — 2026-03-22

## Prompt type
PLAN

## Roadmap item
Governed Prompt Queue — blocked-item recovery policy slice

## Objective
Implement a deterministic, fail-closed blocked-item recovery policy that classifies blocked work items, emits a schema-backed recovery decision artifact, and applies bounded queue recovery only for explicitly recoverable cases.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-BLOCKED-RECOVERY-2026-03-22.md | CREATE | Required PLAN artifact before BUILD execution |
| PLANS.md | MODIFY | Register active plan entry |
| contracts/schemas/prompt_queue_blocked_recovery_decision.schema.json | CREATE | New governed contract for blocked recovery decisions |
| contracts/examples/prompt_queue_blocked_recovery_decision.json | CREATE | Golden-path example for new contract |
| contracts/schemas/prompt_queue_work_item.schema.json | MODIFY | Add nullable blocked recovery decision artifact path |
| contracts/schemas/prompt_queue_state.schema.json | MODIFY | Mirror work-item schema field in queue-state contract |
| contracts/examples/prompt_queue_work_item.json | MODIFY | Keep work-item example schema-valid with new field |
| contracts/examples/prompt_queue_state.json | MODIFY | Keep queue-state example schema-valid with new field |
| contracts/standards-manifest.json | MODIFY | Register new contract + manifest version bump |
| spectrum_systems/modules/prompt_queue/queue_models.py | MODIFY | Add work-item model field and constructor default |
| spectrum_systems/modules/prompt_queue/blocked_recovery_policy.py | CREATE | Pure deterministic classification and decision generation |
| spectrum_systems/modules/prompt_queue/blocked_recovery_artifact_io.py | CREATE | Pure schema validation + artifact write/read utilities |
| spectrum_systems/modules/prompt_queue/blocked_recovery_queue_integration.py | CREATE | Deterministic queue mutation integration for recoverable actions |
| spectrum_systems/modules/prompt_queue/__init__.py | MODIFY | Export blocked recovery APIs |
| scripts/run_prompt_queue_blocked_recovery.py | CREATE | Thin CLI for blocked recovery flow |
| tests/test_prompt_queue_blocked_recovery.py | CREATE | Focused unit/integration tests for blocked recovery guarantees |
| docs/reviews/governed_prompt_queue_blocked_recovery_report.md | CREATE | Mandatory implementation report artifact |

## Contracts touched
- `prompt_queue_blocked_recovery_decision` (new)
- `prompt_queue_work_item` (additive field)
- `prompt_queue_state` (additive field)
- `contracts/standards-manifest.json` (version + registry entry)

## Tests that must pass after execution
1. `pytest -q tests/test_prompt_queue_blocked_recovery.py`
2. `pytest -q tests/test_prompt_queue_loop_continuation.py tests/test_prompt_queue_findings_reentry.py tests/test_prompt_queue_review_parsing_handoff.py tests/test_prompt_queue_live_review_invocation.py tests/test_prompt_queue_review_trigger.py tests/test_prompt_queue_loop_control.py tests/test_prompt_queue_execution.py`
3. `pytest -q tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`

## Scope exclusions
Explicitly list things that are NOT in scope for this plan.

- Do not implement retries or retry scheduling.
- Do not implement queue-wide scheduling or global queue orchestration changes.
- Do not modify provider invocation behavior.
- Do not implement PR automation/UI/operator tooling.
- Do not redesign existing queue lifecycle beyond minimal blocked recovery support.

## Dependencies
List any prior roadmap items that must be complete before this plan can execute.

- Existing governed prompt queue MVP lifecycle and artifact slices must remain intact and are treated as upstream dependencies.
