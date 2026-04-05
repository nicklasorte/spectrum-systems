# Plan — BATCH-FRE-01 — 2026-04-05

## Prompt type
PLAN

## Roadmap item
BATCH-FRE-01 (FRE-001, FRE-002, FRE-003)

## Objective
Implement a deterministic, schema-backed failure diagnosis engine that normalizes governed failure inputs, classifies root causes, and emits a canonical replayable diagnosis artifact without applying repairs.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-FRE-01-2026-04-05.md | CREATE | Required plan-first declaration for multi-file contract + module + test work. |
| PLANS.md | MODIFY | Register this active plan in the repository plan index. |
| contracts/schemas/failure_diagnosis_artifact.schema.json | CREATE | Canonical schema for FRE-003 diagnosis artifact contract. |
| contracts/examples/failure_diagnosis_artifact.json | CREATE | Golden-path example for diagnosis artifact replay and validation. |
| contracts/examples/failure_diagnosis_artifact.example.json | CREATE | Golden-path fixture required by repository golden-path validation workflow. |
| contracts/standards-manifest.json | MODIFY | Publish new contract entry and bump manifest version fields. |
| spectrum_systems/modules/runtime/failure_diagnosis_engine.py | CREATE | Deterministic FRE intake/classification/artifact emission engine. |
| scripts/build_failure_diagnosis_artifact.py | CREATE | Thin CLI entrypoint for governed script/runtime invocation. |
| tests/fixtures/failure_diagnosis/preflight_missing_control_input.json | CREATE | Deterministic fixture for control-surface input-missing diagnosis case. |
| tests/fixtures/failure_diagnosis/manifest_registry_mismatch.json | CREATE | Deterministic fixture for manifest mismatch diagnosis case. |
| tests/fixtures/failure_diagnosis/schema_example_drift.json | CREATE | Deterministic fixture for schema/example drift diagnosis case. |
| tests/fixtures/failure_diagnosis/test_expectation_drift.json | CREATE | Deterministic fixture for test expectation drift diagnosis case. |
| tests/fixtures/failure_diagnosis/invariant_violation.json | CREATE | Deterministic fixture for invariant violation diagnosis case. |
| tests/test_failure_diagnosis_engine.py | CREATE | Focused FRE tests covering required failure classes, determinism, and fail-closed behavior. |

## Contracts touched
- Create `failure_diagnosis_artifact` schema (1.0.0).
- Update `contracts/standards-manifest.json` version fields and add contract registration entry.

## Tests that must pass after execution
1. `pytest tests/test_failure_diagnosis_engine.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/verify-changed-scope/run.sh` with `PLAN_FILES` set to declared files.

## Scope exclusions
- Do not implement repair generation or repair execution.
- Do not modify existing preflight/control/certification semantics.
- Do not add autonomous self-healing behavior.
- Do not refactor unrelated runtime modules.

## Dependencies
- None.
