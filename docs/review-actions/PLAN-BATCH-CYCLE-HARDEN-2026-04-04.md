# Plan — BATCH-CYCLE-HARDEN — 2026-04-04

## Prompt type
PLAN

## Roadmap item
BATCH-CYCLE-HARDEN — Bounded Loop Integrity Hardening

## Objective
Close bounded cycle-loop integrity gaps by hardening continuation depth bounds, deterministic timestamp handling, blocker/review semantics, provenance validation, execution policy contract validation, and replay/error surfaces without expanding architecture.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-CYCLE-HARDEN-2026-04-04.md | CREATE | Required PLAN-first artifact for multi-file + contract changes. |
| PLANS.md | MODIFY | Register active BATCH-CYCLE-HARDEN plan. |
| contracts/schemas/next_cycle_input_bundle.schema.json | MODIFY | Add continuation/provenance/review separation fields and requirements. |
| contracts/schemas/cycle_runner_result.schema.json | MODIFY | Add structured error/replay fields and refusal severity semantics. |
| contracts/schemas/execution_policy.schema.json | CREATE | Add schema-bound execution policy contract and fail-closed validation surface. |
| contracts/examples/next_cycle_input_bundle.json | MODIFY | Keep golden-path example aligned with updated input bundle contract. |
| contracts/examples/cycle_runner_result.json | MODIFY | Keep golden-path example aligned with updated runner result contract. |
| contracts/examples/execution_policy.json | CREATE | Provide contract example for execution policy validation. |
| contracts/standards-manifest.json | MODIFY | Version/pin updates for contract changes and new execution_policy artifact. |
| spectrum_systems/modules/runtime/system_cycle_operator.py | MODIFY | Enforce blocker/review semantics, continuation depth propagation, policy validation, and source provenance in bundle creation. |
| spectrum_systems/modules/runtime/next_governed_cycle_runner.py | MODIFY | Enforce bounded continuation depth/provenance, remove timestamp fallback behavior, add structured error handling + replay entry point, and tighten exception handling. |
| tests/test_system_cycle_operator.py | MODIFY | Add/update tests for bundle semantics, execution policy validation, continuation depth propagation, and determinism. |
| tests/test_next_governed_cycle_runner.py | MODIFY | Add/update tests for depth enforcement, provenance checks, replay/error surfaces, and deterministic runner results. |
| tests/test_roadmap_multi_batch_executor.py | MODIFY | Add policy contract validation coverage as needed at multi-batch seam. |

## Contracts touched
- `next_cycle_input_bundle` (schema + example + manifest entry)
- `cycle_runner_result` (schema + example + manifest entry)
- `execution_policy` (new schema + example + manifest entry)

## Tests that must pass after execution
1. `pytest tests/test_next_governed_cycle_runner.py`
2. `pytest tests/test_system_cycle_operator.py`
3. `pytest tests/test_roadmap_multi_batch_executor.py`
4. `pytest tests/test_system_mvp_validation.py`
5. `pytest tests/test_contracts.py`
6. `pytest tests/test_contract_enforcement.py`
7. `python scripts/run_contract_enforcement.py`
8. `PLAN_FILES="docs/review-actions/PLAN-BATCH-CYCLE-HARDEN-2026-04-04.md PLANS.md contracts/schemas/next_cycle_input_bundle.schema.json contracts/schemas/cycle_runner_result.schema.json contracts/schemas/execution_policy.schema.json contracts/examples/next_cycle_input_bundle.json contracts/examples/cycle_runner_result.json contracts/examples/execution_policy.json contracts/standards-manifest.json spectrum_systems/modules/runtime/system_cycle_operator.py spectrum_systems/modules/runtime/next_governed_cycle_runner.py tests/test_system_cycle_operator.py tests/test_next_governed_cycle_runner.py tests/test_roadmap_multi_batch_executor.py" .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign bounded cycle architecture.
- Do not add new runtime capabilities beyond integrity hardening requirements.
- Do not refactor unrelated modules, contracts, or test suites.

## Dependencies
- `docs/review-actions/PLAN-BATCH-CYCLE-LOOP-2026-04-04.md` must remain authoritative for existing bounded cycle baseline behavior.
