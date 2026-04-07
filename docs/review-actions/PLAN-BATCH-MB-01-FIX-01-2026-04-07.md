# Plan — BATCH-MB-01-FIX-01 — 2026-04-07

## Prompt type
PLAN

## Roadmap item
BATCH-MB-01-FIX-01 — Failure Class Propagation Repair

## Objective
Propagate the canonical MB-01 failure class registry across runtime producers/consumers, schemas, fixtures, and tests so all failure-class handling is deterministic and legacy classes are fully removed.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-MB-01-FIX-01-2026-04-07.md | CREATE | Required PLAN artifact for multi-file fix. |
| spectrum_systems/modules/runtime/recovery_orchestrator.py | MODIFY | Accept/emit canonical failure classes and remove legacy enum dependencies. |
| spectrum_systems/modules/runtime/repair_prompt_generator.py | MODIFY | Add deterministic template mapping for all canonical failure classes. |
| spectrum_systems/modules/runtime/system_end_to_end_validator.py | MODIFY | Ensure downstream consumption supports canonical classes. |
| contracts/schemas/recovery_result_artifact.schema.json | MODIFY | Replace legacy failure_class enum with canonical registry classes. |
| contracts/schemas/repair_prompt_artifact.schema.json | MODIFY | Replace legacy root-cause enum with canonical classes. |
| contracts/examples/recovery_result_artifact.json | MODIFY | Keep golden-path example aligned with new enums. |
| contracts/examples/repair_prompt_artifact.json | MODIFY | Keep golden-path example aligned with new enums. |
| contracts/examples/failure_diagnosis_artifact.example.json | MODIFY | Remove legacy class values from auxiliary diagnosis example. |
| tests/fixtures/failure_diagnosis/manifest_registry_mismatch.json | MODIFY | Migrate fixture semantics to canonical class vocabulary inputs. |
| tests/fixtures/failure_diagnosis/schema_example_drift.json | MODIFY | Migrate fixture semantics to canonical class vocabulary inputs. |
| tests/test_failure_diagnosis_engine.py | MODIFY | Update assertions to canonical classes. |
| tests/test_recovery_orchestrator.py | MODIFY | Update assertions/fixtures for canonical classes. |
| tests/test_repair_prompt_generator.py | MODIFY | Update expected template mapping for canonical classes. |
| tests/test_system_end_to_end_governed_loop.py | MODIFY | Ensure end-to-end expectations reflect canonical classes. |

## Contracts touched
- recovery_result_artifact (updated)
- repair_prompt_artifact (updated)

## Tests that must pass after execution
1. `pytest tests/test_failure_diagnosis_engine.py`
2. `pytest tests/test_recovery_orchestrator.py`
3. `pytest tests/test_repair_prompt_generator.py`
4. `pytest tests/test_system_end_to_end_governed_loop.py`
5. `python scripts/run_contract_preflight.py --base-ref "7cdff9dc87b1b48a9444a428dad898cada74a788" --head-ref "$(git rev-parse HEAD)" --output-dir outputs/contract_preflight`
6. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not add or reintroduce legacy failure class vocabulary.
- Do not create dual-class compatibility layers.
- Do not modify unrelated systems or modules.

## Dependencies
- Existing MB-01 registry remains source of truth (`failure_class_registry`).
