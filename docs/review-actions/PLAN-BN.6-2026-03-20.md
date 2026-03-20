# Plan — BN.6 Control Signal Consumption Layer — 2026-03-20

## Prompt type
PLAN

## Roadmap item
BN.6 — Control Signal Consumption Layer

## Objective
Operationalize BN.5 control signals into deterministic, fail-closed execution behavior consumed by downstream runtime components and CLI flows.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| contracts/schemas/control_execution_result.schema.json | CREATE | Governed contract for BN.6 execution result artifact. |
| contracts/standards-manifest.json | MODIFY | Register control_execution_result contract version per contract authority rules. |
| spectrum_systems/modules/runtime/control_executor.py | CREATE | Implement BN.6 control signal execution layer and diagnostics APIs. |
| spectrum_systems/modules/runtime/control_chain.py | MODIFY | Add optional integration hook to execute control signals without breaking existing behavior. |
| scripts/run_slo_control_chain.py | MODIFY | Add `--execute` path and deterministic execution summary output. |
| tests/test_control_executor.py | CREATE | Add deterministic BN.6 coverage including mode mapping, fail-closed behavior, integration, and idempotence. |
| docs/design/slo-control-system.md | MODIFY | Document BN.6 lifecycle, control signal consumption behavior, and mode examples. |
| PLANS.md | MODIFY | Register this active plan in the active plans table. |

## Contracts touched
- Create `contracts/schemas/control_execution_result.schema.json` at version `1.0.0`.
- Add `control_execution_result` to `contracts/standards-manifest.json`.

## Tests that must pass after execution
1. `pytest tests/test_control_executor.py`
2. `pytest tests/test_control_signals.py tests/test_slo_control_chain.py`
3. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
4. `python scripts/run_contract_enforcement.py`
5. `.codex/skills/contract-boundary-audit/run.sh`

## Scope exclusions
- Do not alter BN.4/BN.5 decision semantics or existing reason-code vocabularies.
- Do not refactor unrelated runtime modules.
- Do not introduce external service integration for escalation/review/rerun actions.

## Dependencies
- BN.5 control signal emission must remain as the upstream signal producer.
