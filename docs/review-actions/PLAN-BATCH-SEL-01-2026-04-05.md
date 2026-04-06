# Plan — BATCH-SEL-01 — 2026-04-05

## Prompt type
PLAN

## Roadmap item
BATCH-SEL-01 (SEL-001)

## Objective
Implement a deterministic fail-closed System Enforcement Layer module and contract surface that blocks any non-governed execution/consumption path unless PQX/TPA/FRE/RIL boundaries and governance evidence are satisfied.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-BATCH-SEL-01-2026-04-05.md | CREATE | Required plan-first declaration for this multi-file SEL build slice. |
| spectrum_systems/modules/runtime/system_enforcement_layer.py | CREATE | Implement explicit fail-closed boundary enforcement for PQX, TPA, FRE, RIL, artifacts, governance evidence, and lineage. |
| contracts/schemas/system_enforcement_result_artifact.schema.json | CREATE | Define authoritative SEL-001 output artifact contract. |
| contracts/examples/system_enforcement_result_artifact.json | CREATE | Provide canonical golden-path example for SEL output artifact. |
| contracts/standards-manifest.json | MODIFY | Register system_enforcement_result_artifact contract metadata/version pin. |
| tests/test_system_enforcement_layer.py | CREATE | Deterministic fail-closed tests covering governed allow path and required block scenarios. |

## Contracts touched
- Create `system_enforcement_result_artifact` schema (1.0.0).
- Update `contracts/standards-manifest.json` with contract registration metadata.

## Tests that must pass after execution
1. `pytest tests/test_system_enforcement_layer.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not introduce bypass flags, warn-only modes, or hidden allow paths.
- Do not duplicate business logic from PQX/TPA/FRE/RIL modules; only enforce boundary evidence/presence.
- Do not redefine authority semantics beyond existing governed boundary requirements.
- Do not refactor unrelated runtime modules, contracts, or tests.

## Dependencies
- Existing PQX execution policy and required context enforcement remain the entry authority source.
- Existing RIL-004 projection artifact contracts remain the downstream intake authority source.
