# Plan — BATCH-LTV-C — 2026-04-04

## Prompt type
PLAN

## Roadmap item
BATCH-LTV-C — Entropy Detection + Roadmap Steering (LT-07 + LT-08 + LT-10)

## Objective
Add deterministic drift classification, artifact aging posture, and roadmap steering signals that fail closed and directly influence governed batch selection.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-LTV-C-2026-04-04.md | CREATE | Required plan artifact before multi-file BUILD work |
| contracts/schemas/drift_detection_record.schema.json | CREATE | Contract for LT-07 drift findings artifact |
| contracts/schemas/artifact_lifecycle_status_record.schema.json | CREATE | Contract for LT-08 artifact aging and brownfield lifecycle state |
| contracts/schemas/roadmap_signal_bundle.schema.json | CREATE | Contract for LT-10 deterministic roadmap feeder output |
| contracts/examples/drift_detection_record.json | CREATE | Golden-path example for drift detection record |
| contracts/examples/artifact_lifecycle_status_record.json | CREATE | Golden-path example for lifecycle aging status |
| contracts/examples/roadmap_signal_bundle.json | CREATE | Golden-path example for roadmap feeder bundle |
| contracts/standards-manifest.json | MODIFY | Register new contracts and increment manifest versions |
| spectrum_systems/modules/runtime/roadmap_signal_steering.py | CREATE | Deterministic runtime builders for drift, lifecycle, feeder, and steering priority logic |
| spectrum_systems/modules/runtime/roadmap_selector.py | MODIFY | Integrate roadmap signal bundle steering, freeze/block overrides, and fail-closed signal requirements |
| tests/test_roadmap_signal_steering.py | CREATE | Unit coverage for classification, lifecycle aging, feeder outputs, steering priorities, and freeze/block behavior |
| tests/test_roadmap_selector.py | MODIFY | Integration coverage for roadmap steering behavior in selection outputs |

## Contracts touched
- New: `drift_detection_record`
- New: `artifact_lifecycle_status_record`
- New: `roadmap_signal_bundle`
- Modified: `standards_manifest` version and contract registry entries

## Tests that must pass after execution
1. `pytest tests/test_roadmap_signal_steering.py tests/test_roadmap_selector.py tests/test_contracts.py tests/test_contract_enforcement.py`
2. `python scripts/run_contract_enforcement.py`
3. `pytest`
4. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign roadmap data model beyond deterministic steering signals.
- Do not add model-based or probabilistic control logic.
- Do not alter unrelated runtime orchestration modules.

## Dependencies
- Existing roadmap selector and runtime governance contracts remain authoritative inputs.
