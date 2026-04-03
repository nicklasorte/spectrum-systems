# Plan — BATCH-U — 2026-04-03

## Prompt type
PLAN

## Roadmap item
BATCH-U — Operator / Usability Layer

## Objective
Provide a deterministic one-command operator cycle that runs roadmap selection/authorization/bounded execution/integration validation and emits governed build + next-step summary artifacts.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-U-2026-04-03.md | CREATE | Required plan-first artifact for this multi-file implementation slice. |
| PLANS.md | MODIFY | Register active BATCH-U plan entry. |
| contracts/schemas/next_step_recommendation.schema.json | CREATE | Contract-first schema for next-step recommendation artifact emitted by operator cycle. |
| contracts/schemas/build_summary.schema.json | CREATE | Contract-first schema for build summary artifact emitted by operator cycle. |
| contracts/standards-manifest.json | MODIFY | Register new schema contracts with canonical version pins. |
| contracts/examples/next_step_recommendation.json | CREATE | Golden-path example payload for next_step_recommendation contract. |
| contracts/examples/build_summary.json | CREATE | Golden-path example payload for build_summary contract. |
| spectrum_systems/modules/runtime/system_cycle_operator.py | CREATE | Implement run_system_cycle(...) orchestration and failure-surface normalization. |
| scripts/run_system_cycle.py | CREATE | Provide minimal one-command operator interface for full bounded cycle execution. |
| tests/test_system_cycle_operator.py | CREATE | Deterministic coverage for full cycle, artifacts, next-step recommendation, and failure clarity. |

## Contracts touched
- `contracts/schemas/next_step_recommendation.schema.json` (new)
- `contracts/schemas/build_summary.schema.json` (new)
- `contracts/standards-manifest.json` (new contract entries + version bump)

## Tests that must pass after execution
1. `pytest tests/test_system_cycle_operator.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `pytest tests/test_roadmap_multi_batch_executor.py tests/test_system_integration_validator.py`

## Scope exclusions
- Do not change core roadmap execution semantics in existing RDX modules.
- Do not change authority precedence model across PRG/RVW/CTX/TPA/control seams.
- Do not add external service dependencies or network calls.

## Dependencies
- `docs/review-actions/PLAN-RDX-006-2026-04-03.md` must remain valid and bounded execution semantics preserved.
- `docs/review-actions/PLAN-BATCH-Z-2026-04-03.md` integration validator contract/module must remain source-of-truth.
