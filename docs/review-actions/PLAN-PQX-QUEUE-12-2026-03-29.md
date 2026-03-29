# Plan — PQX-QUEUE-12 — 2026-03-29

## Prompt type
PLAN

## Roadmap item
[ROW: QUEUE-12] Queue Policy Backtesting

## Objective
Implement deterministic, fail-closed prompt-queue policy backtesting over historical/replay artifacts with explicit comparison reporting and no live queue mutation.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-PQX-QUEUE-12-2026-03-29.md | CREATE | Required plan-first record for multi-file BUILD slice. |
| contracts/schemas/prompt_queue_policy_backtest_report.schema.json | CREATE | Define authoritative contract for queue policy backtest reporting artifact. |
| contracts/examples/prompt_queue_policy_backtest_report.json | CREATE | Provide golden-path contract example for validation and downstream reuse. |
| contracts/standards-manifest.json | MODIFY | Register new contract and bump manifest publication version metadata. |
| spectrum_systems/modules/prompt_queue/policy_backtesting.py | CREATE | Implement deterministic, fail-closed queue policy backtesting seam. |
| spectrum_systems/modules/prompt_queue/queue_artifact_io.py | MODIFY | Add schema validation helper for policy backtest report artifact. |
| spectrum_systems/modules/prompt_queue/__init__.py | MODIFY | Export queue policy backtesting public API helpers. |
| scripts/run_prompt_queue_policy_backtest.py | CREATE | Add thin CLI wrapper around queue policy backtesting seam. |
| tests/test_prompt_queue_policy_backtesting.py | CREATE | Add deterministic/fail-closed seam and CLI coverage for QUEUE-12. |
| tests/test_contracts.py | MODIFY | Validate new contract example through existing contract test surface. |

## Contracts touched
- New: `prompt_queue_policy_backtest_report` schema + example.
- Modified registry: `contracts/standards-manifest.json`.

## Tests that must pass after execution
1. `pytest tests/test_prompt_queue_policy_backtesting.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not change queue execution/state machine behavior.
- Do not change replay engine runtime semantics.
- Do not auto-activate or mutate policy registry defaults.
- Do not introduce multi-queue scheduling or live execution hooks.

## Dependencies
- QUEUE-08 replay/resume artifacts must remain authoritative inputs.
- QUEUE-10 certification and QUEUE-11 audit artifacts must remain read-only evidence surfaces.
