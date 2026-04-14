# Plan — TEST-INTEGRITY-HARDENING — 2026-04-14

## Prompt type
BUILD

## Roadmap item
Bounded repo-native hardening slice for pytest discovery and inventory integrity gate

## Objective
Restore deterministic pytest discovery/collection behavior for PR preflight and add a fail-closed, classified test-inventory integrity gate that blocks silent scope regressions.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| scripts/run_contract_preflight.py | MODIFY | Diagnose and classify pytest discovery/inventory failures with governed enforcement outputs. |
| spectrum_systems/modules/runtime/test_inventory_integrity.py | CREATE | Pure validator for pytest config/discovery/inventory integrity classification and artifact creation. |
| contracts/schemas/test_inventory_integrity_result.schema.json | CREATE | Governed schema for deterministic integrity artifact. |
| contracts/examples/test_inventory_integrity_result.json | CREATE | Canonical passing example artifact payload. |
| docs/governance/test_inventory_integrity.md | CREATE | Operator documentation for cause, detection classes, repair path, and baseline refresh flow. |
| docs/governance/pytest_pr_inventory_baseline.json | CREATE | Deterministic baseline node inventory for PR/default suite integrity checks. |
| tests/test_test_inventory_integrity.py | CREATE | Focused unit coverage for integrity classifier and baseline refresh behavior. |
| tests/test_contract_preflight.py | MODIFY | Ensure preflight surfaces classified test-integrity failures and blocking behavior. |
| tests/test_contracts.py | MODIFY | Validate new schema and example are governed and loadable. |
| contracts/standards-manifest.json | MODIFY | Register new test integrity contract artifact. |

## Contracts touched
- `contracts/schemas/test_inventory_integrity_result.schema.json` (new)
- `contracts/standards-manifest.json` (new contract registration)

## Tests that must pass after execution
1. `pytest --collect-only -q`
2. `pytest tests/test_contract_preflight.py -q`
3. `pytest tests/test_system_registry_boundaries.py -q`
4. `pytest tests/test_system_handoff_integrity.py -q`
5. `pytest tests/test_top_level_conductor.py -q`
6. `pytest tests/test_github_closure_continuation.py -q`
7. `pytest tests/test_pre_pr_repair_loop.py -q`
8. `pytest tests/test_roadmap_execution.py -q`
9. `pytest`

## Scope exclusions
- Do not redesign the overall preflight orchestration architecture.
- Do not remove/disable existing tests.
- Do not introduce new 3-letter systems unless existing ownership cannot support this slice.

## Dependencies
- Existing contract preflight flow in `scripts/run_contract_preflight.py` must remain authoritative.
- Ownership boundaries must remain aligned with `docs/architecture/system_registry.md`.
