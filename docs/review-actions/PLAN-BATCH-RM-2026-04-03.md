# Plan — BATCH-RM — 2026-04-03

## Prompt type
PLAN

## Roadmap item
BATCH-RM — Remediation Automation Layer

## Objective
Add deterministic remediation-plan generation and wiring into next-step recommendation artifacts so blocked runs include structured, traceable remediation guidance.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-RM-2026-04-03.md | CREATE | Required plan-first artifact for this batch. |
| PLANS.md | MODIFY | Register this active plan in the repository plan index. |
| contracts/schemas/next_step_recommendation.schema.json | MODIFY | Add remediation plan reference and structured remediation steps contract fields. |
| contracts/examples/next_step_recommendation.json | MODIFY | Keep golden-path example aligned with schema additions. |
| contracts/standards-manifest.json | MODIFY | Bump next_step_recommendation schema version metadata. |
| spectrum_systems/modules/runtime/system_cycle_operator.py | MODIFY | Generate deterministic remediation plan artifact, repeated-pattern reuse, and next-step integration. |
| tests/test_system_cycle_operator.py | MODIFY | Add deterministic remediation generation and integration coverage. |

## Contracts touched
- `contracts/schemas/next_step_recommendation.schema.json` (additive change)
- `contracts/standards-manifest.json` (version metadata update)

## Tests that must pass after execution
1. `pytest tests/test_system_cycle_operator.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/contract-boundary-audit/run.sh next_step_recommendation`

## Scope exclusions
- Do not modify bounded multi-batch execution semantics in `roadmap_multi_batch_executor.py`.
- Do not introduce automatic code-fix execution; remediation output remains advisory.
- Do not modify unrelated contracts or module boundaries.

## Dependencies
- BATCH-U/BATCH-Y recommendation and summary contracts must remain authoritative and backward compatible.
