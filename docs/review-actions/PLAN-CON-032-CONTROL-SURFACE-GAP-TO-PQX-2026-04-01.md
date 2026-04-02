# Plan — CON-032 Control Surface Gap → PQX Triage Integration — 2026-04-01

## Prompt type
PLAN

## Roadmap item
CON-032 — Control Surface Gap → PQX Triage Integration

## Objective
Convert control-surface manifest/enforcement/obedience failures into deterministic, schema-valid gap artifacts and fail-closed PQX triage work items that are wired into preflight blocking behavior.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CON-032-CONTROL-SURFACE-GAP-TO-PQX-2026-04-01.md | CREATE | Required PLAN artifact before multi-file contract/module wiring work. |
| PLANS.md | MODIFY | Register active CON-032 plan in plan index. |
| contracts/schemas/control_surface_gap_result.schema.json | CREATE | Governed schema for deterministic machine-readable control-surface gaps. |
| contracts/examples/control_surface_gap_result.json | CREATE | Golden-path example for gap result contract. |
| contracts/schemas/contract_preflight_result_artifact.schema.json | MODIFY | Allow preflight artifact to carry control-surface gap/PQX triage evidence. |
| contracts/examples/contract_preflight_result_artifact.json | MODIFY | Keep contract example aligned with preflight schema extension. |
| spectrum_systems/modules/runtime/control_surface_gap_extractor.py | CREATE | Deterministic fail-closed extraction of manifest/enforcement/obedience gaps. |
| spectrum_systems/modules/runtime/control_surface_gap_to_pqx.py | CREATE | Deterministic adapter mapping gaps to PQX-compatible triage work items. |
| scripts/run_control_surface_gap_extraction.py | CREATE | CLI for extraction, schema validation, PQX conversion, and fail-closed exits. |
| scripts/run_contract_preflight.py | MODIFY | Wire gap extraction + PQX conversion into preflight and enforce blocking conditions. |
| tests/test_control_surface_gap_extractor.py | CREATE | Unit coverage for extraction logic, deduping, determinism, and fail-closed behavior. |
| tests/test_control_surface_gap_to_pqx.py | CREATE | Unit coverage for gap→PQX conversion correctness and failure conditions. |
| tests/test_contract_preflight.py | MODIFY | Validate preflight integration behavior for blocker gaps and conversion failures. |
| tests/test_contracts.py | MODIFY | Validate new control_surface_gap_result example contract. |

## Contracts touched
- `contracts/schemas/control_surface_gap_result.schema.json` (new, v1.0.0)
- `contracts/schemas/contract_preflight_result_artifact.schema.json` (extended with optional gap/PQX fields)

## Tests that must pass after execution
1. `pytest -q tests/test_control_surface_gap_extractor.py tests/test_control_surface_gap_to_pqx.py tests/test_contract_preflight.py`
2. `pytest -q tests/test_contracts.py tests/test_control_surface_enforcement.py`
3. `python scripts/run_control_surface_gap_extraction.py --manifest contracts/examples/control_surface_manifest.json --enforcement contracts/examples/control_surface_enforcement_result.json --obedience contracts/examples/control_surface_obedience_result.json --output-dir outputs/control_surface_gap`
4. `python scripts/run_contract_preflight.py --changed-path spectrum_systems/modules/runtime/control_surface_gap_extractor.py --changed-path spectrum_systems/modules/runtime/control_surface_gap_to_pqx.py --changed-path scripts/run_control_surface_gap_extraction.py --changed-path scripts/run_contract_preflight.py --changed-path contracts/schemas/control_surface_gap_result.schema.json --changed-path contracts/examples/control_surface_gap_result.json --changed-path tests/test_control_surface_gap_extractor.py --changed-path tests/test_control_surface_gap_to_pqx.py`
5. `PLAN_FILES='PLANS.md docs/review-actions/PLAN-CON-032-CONTROL-SURFACE-GAP-TO-PQX-2026-04-01.md contracts/schemas/control_surface_gap_result.schema.json contracts/examples/control_surface_gap_result.json contracts/schemas/contract_preflight_result_artifact.schema.json contracts/examples/contract_preflight_result_artifact.json spectrum_systems/modules/runtime/control_surface_gap_extractor.py spectrum_systems/modules/runtime/control_surface_gap_to_pqx.py scripts/run_control_surface_gap_extraction.py scripts/run_contract_preflight.py tests/test_control_surface_gap_extractor.py tests/test_control_surface_gap_to_pqx.py tests/test_contract_preflight.py tests/test_contracts.py' .codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not redesign or alter PQX core planning/execution modules.
- Do not introduce heuristic control-surface inference.
- Do not weaken existing enforcement/obedience fail-closed semantics.
- Do not add unrelated refactors outside declared files.

## Dependencies
- CON-029 control surface manifest artifact and schema.
- CON-030 control surface enforcement artifact and schema.
- CON-031 control surface obedience artifact and schema.
