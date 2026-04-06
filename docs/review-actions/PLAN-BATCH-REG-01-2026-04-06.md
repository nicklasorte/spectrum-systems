# Plan — BATCH-REG-01 — 2026-04-06

## Prompt type
PLAN

## Roadmap item
BATCH-REG-01 (REG-001)

## Objective
Create a canonical system registry boundary layer with schema-backed artifact, example payload, and deterministic tests enforcing single-ownership and anti-duplication invariants.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-REG-01-2026-04-06.md | CREATE | Required plan artifact prior to multi-file BUILD scope. |
| docs/architecture/system_registry.md | CREATE | Canonical human-readable system registry and hard-boundary definitions. |
| contracts/schemas/system_registry_artifact.schema.json | CREATE | Contract-first schema for the machine-readable registry artifact. |
| contracts/examples/system_registry_artifact.json | CREATE | Golden-path example for the new system registry artifact contract. |
| contracts/standards-manifest.json | MODIFY | Register new artifact type and bump manifest publication version metadata. |
| tests/test_system_registry_boundaries.py | CREATE | Deterministic enforcement tests for ownership uniqueness, invariants, and manifest alignment. |

## Contracts touched
- Create `contracts/schemas/system_registry_artifact.schema.json` (`schema_version` = `1.0.0`)
- Update `contracts/standards-manifest.json` to register `system_registry_artifact`

## Tests that must pass after execution
1. `pytest tests/test_system_registry_boundaries.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/contract-boundary-audit/run.sh`
5. `.codex/skills/verify-changed-scope/run.sh docs/review-actions/PLAN-BATCH-REG-01-2026-04-06.md`

## Scope exclusions
- Do not rename existing systems or artifact types outside this registry layer.
- Do not refactor existing modules or scripts.
- Do not modify unrelated tests or roadmap files.

## Dependencies
- Existing subsystem contracts for PQX, TPA, FRE, RIL, SEL, CDE, TLC, and PRG remain authoritative inputs.
