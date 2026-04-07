# Plan — BATCH-HR-A — 2026-04-07

## Prompt type
PLAN

## Roadmap item
BATCH-HR-A — HR-01 + HR-02 — Canonical Stage Contract Spine + Runtime Enforcement

## Objective
Introduce a strict canonical `stage_contract` schema plus a deterministic runtime transition-readiness evaluator, then wire one existing governed transition seam to consume it in opt-in fail-closed mode.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| contracts/schemas/stage_contract.schema.json | CREATE | Canonical stage contract schema. |
| contracts/examples/stage_contracts/prompt_queue_stage_contract.json | CREATE | Golden-path prompt-queue stage contract fixture. |
| contracts/examples/stage_contracts/pqx_stage_contract.json | CREATE | Golden-path orchestration/PQX stage contract fixture. |
| contracts/standards-manifest.json | MODIFY | Register new `stage_contract` artifact/version metadata. |
| spectrum_systems/modules/runtime/stage_contract_runtime.py | CREATE | Loader/validator/readiness evaluator module with deterministic outputs. |
| spectrum_systems/modules/runtime/__init__.py | MODIFY | Export stage-contract runtime APIs in repo-native module surface. |
| spectrum_systems/orchestration/sequence_transition_policy.py | MODIFY | Add first integration seam: optional contract-based transition gate. |
| tests/test_contracts.py | MODIFY | Add schema/example validation coverage for new contract fixtures. |
| tests/test_stage_contract_runtime.py | CREATE | Unit coverage for loader, validation, readiness semantics, determinism. |
| tests/test_sequence_transition_policy.py | MODIFY | Integration seam coverage proving sequence transition consults stage contract. |
| docs/architecture/stage_contract_spine.md | CREATE | Architecture/design documentation for canonical spine and migration. |
| docs/review-actions/BATCH-HR-A-implementation-report-2026-04-07.md | CREATE | Action report including seam choice and follow-on items. |

## Contracts touched
- `contracts/schemas/stage_contract.schema.json` (new)
- `contracts/standards-manifest.json` (new contract registration/version update)

## Tests that must pass after execution
1. `pytest tests/test_stage_contract_runtime.py tests/test_sequence_transition_policy.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not redesign promotion/control authority models.
- Do not migrate all queue/orchestration subsystems to stage contracts.
- Do not add model-calling behavior in stage contract runtime.
- Do not weaken existing transition gates; only add a narrow opt-in seam.

## Dependencies
- Existing sequence transition policy and trust-spine enforcement paths remain authoritative for promotion.
