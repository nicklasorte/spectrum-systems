# Plan — Prompt BAH Drift Result Contract & Engine Wiring — 2026-03-22

## Prompt type
PLAN

## Roadmap item
Prompt BAH — Drift Detection System

## Objective
Introduce a governed fail-closed `drift_result` contract and deterministic drift detection wiring into BAG replay outputs.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BAH-DRIFT-RESULT-2026-03-22.md | CREATE | Required PLAN artifact before multi-file BUILD work. |
| PLANS.md | MODIFY | Register active BAH drift-result plan entry. |
| contracts/schemas/drift_result.schema.json | CREATE | Define canonical drift_result contract. |
| contracts/examples/drift_result.json | CREATE | Add golden-path example artifact for drift_result. |
| contracts/standards-manifest.json | MODIFY | Register drift_result contract and bump manifest publication version. |
| spectrum_systems/modules/runtime/drift_detection_engine.py | MODIFY | Implement deterministic fail-closed detect_drift API against replay_result contract. |
| spectrum_systems/modules/runtime/replay_engine.py | MODIFY | Attach drift_result artifact after replay_result generation. |
| tests/test_drift_detection_engine.py | MODIFY | Add deterministic classification and fail-closed coverage for detect_drift. |
| tests/test_replay_engine.py | MODIFY | Assert drift_result attachment and correctness on replay outputs. |

## Contracts touched
- drift_result (new contract, schema version 1.0.0)
- standards manifest contract registry update (additive contract publication)

## Tests that must pass after execution
1. `pytest tests/test_drift_detection_engine.py tests/test_replay_engine.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `python scripts/check_artifact_boundary.py`
5. `PLAN_FILES="docs/review-actions/PLAN-BAH-DRIFT-RESULT-2026-03-22.md PLANS.md contracts/schemas/drift_result.schema.json contracts/examples/drift_result.json contracts/standards-manifest.json spectrum_systems/modules/runtime/drift_detection_engine.py spectrum_systems/modules/runtime/replay_engine.py tests/test_drift_detection_engine.py tests/test_replay_engine.py" .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not modify replay_result schema fields for BAG output.
- Do not remove existing drift_detection_result contract artifacts.
- Do not add non-runtime orchestration or governance policy wiring.

## Dependencies
- Prompt BAG replay engine outputs must remain the upstream input contract.
