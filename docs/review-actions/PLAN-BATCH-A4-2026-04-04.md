# Plan — BATCH-A4 — 2026-04-04

## Prompt type
PLAN

## Roadmap item
BATCH-A4 — Roadmap Self-Adaptation

## Objective
Add governed, deterministic roadmap adjustment contracts and runtime logic that derives and applies fail-closed roadmap updates from exception/risk/drift/review signals.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-A4-2026-04-04.md | CREATE | Required plan-first artifact for this multi-file roadmap slice. |
| PLANS.md | MODIFY | Register active BATCH-A4 plan entry. |
| contracts/schemas/roadmap_adjustment_record.schema.json | CREATE | Add strict contract for governed roadmap mutations. |
| contracts/examples/roadmap_adjustment_record.json | CREATE | Golden-path example for contract validation. |
| contracts/standards-manifest.json | MODIFY | Register roadmap_adjustment_record and bump standards version. |
| spectrum_systems/modules/runtime/roadmap_adjustment_engine.py | CREATE | Implement deterministic derive/apply adjustment engine. |
| spectrum_systems/modules/runtime/system_cycle_operator.py | MODIFY | Integrate adjustment derivation/application and expose artifacts in operator outputs. |
| tests/test_roadmap_selector.py | MODIFY | Add selector test asserting adjusted roadmap is used for next selection. |
| tests/test_roadmap_multi_batch_executor.py | MODIFY | Add deterministic adjustment engine behavior tests. |
| tests/test_system_cycle_operator.py | MODIFY | Add integration test that cycle outputs include and use roadmap adjustments. |
| tests/test_contracts.py | MODIFY | Validate new roadmap_adjustment_record example under contract tests. |

## Contracts touched
- New: `roadmap_adjustment_record` (`contracts/schemas/roadmap_adjustment_record.schema.json`)
- Updated manifest: `contracts/standards-manifest.json`

## Tests that must pass after execution
1. `pytest tests/test_roadmap_selector.py`
2. `pytest tests/test_roadmap_multi_batch_executor.py`
3. `pytest tests/test_system_cycle_operator.py`
4. `pytest tests/test_contracts.py`
5. `pytest tests/test_contract_enforcement.py`
6. `python scripts/run_contract_enforcement.py`
7. `pytest`
8. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign roadmap selection policy outside adjustment hooks.
- Do not introduce model-driven control logic or non-deterministic behavior.
- Do not modify unrelated modules, schemas, or roadmap files.

## Dependencies
- BATCH-A3 exception routing outputs available for adjustment input.
- BATCH-S2 eval coverage signal artifacts available for adjustment input.
