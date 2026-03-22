# Plan — Governed Prompt Queue Retry Policy — 2026-03-22

## Prompt type
PLAN

## Roadmap item
Governed Prompt Queue — deterministic retry policy slice

## Objective
Implement deterministic, fail-closed retry policy handling for single work items with schema-backed retry decision artifacts, strict retry budget enforcement, and bounded queue mutation.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-GOVERNED-PROMPT-QUEUE-RETRY-POLICY-2026-03-22.md | CREATE | Required PLAN artifact before BUILD execution |
| PLANS.md | MODIFY | Register active plan entry |
| contracts/schemas/prompt_queue_retry_decision.schema.json | CREATE | New governed contract for retry decisions |
| contracts/examples/prompt_queue_retry_decision.json | CREATE | Golden-path example payload for retry decision contract |
| contracts/schemas/prompt_queue_work_item.schema.json | MODIFY | Add retry state and retry artifact tracking fields |
| contracts/schemas/prompt_queue_state.schema.json | MODIFY | Mirror work-item retry fields in queue-state schema |
| contracts/examples/prompt_queue_work_item.json | MODIFY | Keep work-item example schema-valid with new retry fields |
| contracts/examples/prompt_queue_state.json | MODIFY | Keep queue-state example schema-valid with new retry fields |
| contracts/standards-manifest.json | MODIFY | Register retry-decision contract and bump manifest version |
| spectrum_systems/modules/prompt_queue/queue_models.py | MODIFY | Add minimal retry fields/defaults to work-item model |
| spectrum_systems/modules/prompt_queue/retry_policy.py | CREATE | Pure deterministic retry eligibility policy |
| spectrum_systems/modules/prompt_queue/retry_artifact_io.py | CREATE | Pure retry artifact validation and write/read boundary |
| spectrum_systems/modules/prompt_queue/retry_queue_integration.py | CREATE | Deterministic queue mutation applying retry decisions |
| spectrum_systems/modules/prompt_queue/__init__.py | MODIFY | Export retry policy/artifact/queue integration APIs |
| scripts/run_prompt_queue_retry.py | CREATE | Thin CLI for single-item retry decision + mutation flow |
| tests/test_prompt_queue_retry.py | CREATE | Deterministic retry policy/integration tests |
| docs/reviews/governed_prompt_queue_retry_policy_report.md | CREATE | Mandatory delivery report artifact |

## Contracts touched
- `prompt_queue_retry_decision` (new)
- `prompt_queue_work_item` (additive fields)
- `prompt_queue_state` (additive fields)
- `contracts/standards-manifest.json` (version + contract registry update)

## Tests that must pass after execution
1. `pytest -q tests/test_prompt_queue_retry.py`
2. `pytest -q tests/test_prompt_queue_execution.py tests/test_prompt_queue_loop_control.py tests/test_prompt_queue_blocked_recovery.py`
3. `pytest -q tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`

## Scope exclusions
Explicitly list things that are NOT in scope for this plan.

- Do not add scheduling, backoff, or parallel retry orchestration.
- Do not change provider invocation logic.
- Do not implement multi-item retry chaining.
- Do not redesign broader queue lifecycle state machine.
- Do not implement automatic retry for blocked items.

## Dependencies
List any prior roadmap items that must be complete before this plan can execute.

- Governed prompt queue MVP lifecycle slices (execution, post-execution, loop control, blocked recovery) remain upstream dependencies.
