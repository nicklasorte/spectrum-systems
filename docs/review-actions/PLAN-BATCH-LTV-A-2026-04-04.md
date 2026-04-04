# Plan — BATCH-LTV-A — 2026-04-04

## Prompt type
PLAN

## Roadmap item
BATCH-LTV-A — Brownfield Trust Core (LT-01 + LT-02 + LT-04)

## Objective
Add deterministic judgment lifecycle, precedent selection/conflict artifacts, and override governance hardening with fail-closed integration into governed runtime summaries and handoff surfaces.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-LTV-A-2026-04-04.md | CREATE | Required PLAN-first execution artifact for BATCH-LTV-A. |
| PLANS.md | MODIFY | Register active BATCH-LTV-A plan. |
| contracts/schemas/judgment_lifecycle_record.schema.json | CREATE | New governed contract for explicit judgment lifecycle state and supersession. |
| contracts/schemas/precedent_selection_record.schema.json | CREATE | New governed contract for deterministic precedent selection decisions. |
| contracts/schemas/precedent_conflict_record.schema.json | CREATE | New governed contract for explicit precedent conflict artifacts. |
| contracts/schemas/override_governance_record.schema.json | CREATE | New governed contract for bounded override governance metadata and escalation. |
| contracts/examples/judgment_lifecycle_record.json | CREATE | Golden example payload for judgment lifecycle contract. |
| contracts/examples/precedent_selection_record.json | CREATE | Golden example payload for precedent selection contract. |
| contracts/examples/precedent_conflict_record.json | CREATE | Golden example payload for precedent conflict contract. |
| contracts/examples/override_governance_record.json | CREATE | Golden example payload for override governance contract. |
| contracts/schemas/build_summary.schema.json | MODIFY | Surface lifecycle/precedent/override governance refs in operator summary. |
| contracts/schemas/batch_handoff_bundle.schema.json | MODIFY | Carry unresolved lifecycle/conflict/override governance signals across batches. |
| contracts/examples/build_summary.json | MODIFY | Keep golden example aligned with updated summary contract. |
| contracts/examples/batch_handoff_bundle.json | MODIFY | Keep golden example aligned with updated handoff contract. |
| contracts/standards-manifest.json | MODIFY | Register new contracts and version-bump updated contracts. |
| spectrum_systems/modules/runtime/judgment_engine.py | MODIFY | Add deterministic lifecycle manager, precedent selection/conflict resolution, and override governance helpers/integration. |
| spectrum_systems/modules/runtime/system_cycle_operator.py | MODIFY | Integrate new refs/signals into build_summary and batch_handoff_bundle with fail-closed defaults. |
| tests/test_system_cycle_operator.py | MODIFY | Add assertions for summary/handoff propagation of lifecycle/precedent/override refs. |
| tests/test_roadmap_multi_batch_executor.py | MODIFY | Add propagation assertions on derived handoff bundle path. |
| tests/test_contracts.py | MODIFY | Add validation coverage for new contracts/examples. |
| tests/test_contract_enforcement.py | MODIFY | Add standards-manifest registration checks for new contracts. |
| tests/test_cycle_runner.py | MODIFY | Add deterministic lifecycle/precedent/conflict and override governance fail-closed behavior tests. |

## Contracts touched
- ADD `judgment_lifecycle_record@1.0.0`
- ADD `precedent_selection_record@1.0.0`
- ADD `precedent_conflict_record@1.0.0`
- ADD `override_governance_record@1.0.0`
- UPDATE `build_summary` schema version to include governance refs
- UPDATE `batch_handoff_bundle` schema version to include governance follow-up fields
- UPDATE `contracts/standards-manifest.json` version and contract entries

## Tests that must pass after execution
1. `pytest tests/test_system_cycle_operator.py`
2. `pytest tests/test_roadmap_multi_batch_executor.py`
3. `pytest tests/test_contracts.py`
4. `pytest tests/test_contract_enforcement.py`
5. `python scripts/run_contract_enforcement.py`
6. `pytest`
7. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign existing policy authority model.
- Do not add model-driven control authority or hidden memory surfaces.
- Do not change unrelated module structure or non-governance artifacts.
- Do not add new repositories/modules outside current runtime/contract surfaces.

## Dependencies
- Existing governed runtime operator and judgment engine artifacts must remain contract-valid and deterministic.
