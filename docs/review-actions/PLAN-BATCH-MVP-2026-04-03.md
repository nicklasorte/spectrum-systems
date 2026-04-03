# Plan — BATCH-MVP — 2026-04-03

## Prompt type
PLAN

## Roadmap item
BATCH-MVP — End-to-End System Validation

## Objective
Execute a deterministic multi-cycle governed system run and emit a governed `system_mvp_validation_report` artifact proving end-to-end behavior quality across success, review-trigger, and blocked scenarios.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-MVP-2026-04-03.md | CREATE | Record PLAN-first scope and validation requirements for BATCH-MVP. |
| contracts/schemas/system_mvp_validation_report.schema.json | CREATE | Contract-first schema for governed MVP validation output artifact. |
| contracts/examples/system_mvp_validation_report.json | CREATE | Golden-path example payload for MVP validation report contract. |
| contracts/standards-manifest.json | MODIFY | Register the new contract and bump manifest version metadata. |
| spectrum_systems/modules/runtime/system_mvp_validation.py | CREATE | Deterministic BATCH-MVP execution module running 3–5+ `run_system_cycle(...)` iterations and producing report artifact. |
| tests/test_system_mvp_validation.py | CREATE | Deterministic behavior and output-structure stability tests for MVP validation execution/report emission. |
| tests/test_contracts.py | MODIFY | Validate the new `system_mvp_validation_report` contract example. |

## Contracts touched
- `system_mvp_validation_report` (new)
- `standards_manifest` version metadata and contract registry entry

## Tests that must pass after execution
1. `pytest tests/test_system_mvp_validation.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/contract-boundary-audit/run.sh`
5. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not modify existing runtime decision logic in `run_system_cycle`.
- Do not alter roadmap architecture or lifecycle state machinery.
- Do not add non-deterministic inputs or network-dependent validation.

## Dependencies
- `run_system_cycle` operator seam from BATCH-U must remain the execution backbone.
- Existing governed artifacts (`build_summary`, `next_step_recommendation`, `trace_navigation`, `core_system_integration_validation`, adaptive execution artifacts) must be consumed as-is.
