# Plan — RAX-02-REAL — 2026-04-11

## Prompt type
BUILD

## Scope
Implement a thin roadmap realization execution surface for RF-02 and RF-03 only, using strict fail-closed checks backed by `roadmap_step_contract` artifacts and behavioral-test gating.

## Files expected to change
| Path | Action | Purpose |
| --- | --- | --- |
| `scripts/roadmap_realization_runner.py` | CREATE | Add deterministic runner for RF-02 and RF-03 contract realization checks and status updates. |
| `artifacts/roadmap_contracts/RF-02.json` | CREATE | Add RF-02 enriched roadmap step contract instance. |
| `artifacts/roadmap_contracts/RF-03.json` | CREATE | Add RF-03 enriched roadmap step contract instance. |
| `spectrum_systems/modules/runtime/roadmap_realization_runtime.py` | CREATE | Add strict dependency and status transition helpers used by runner. |
| `tests/test_roadmap_realization_runner.py` | CREATE | Add focused tests for schema validation, dependencies, forbidden patterns, entrypoint checks, and status advancement gating. |

## Execution steps
1. Implement runtime helper functions that enforce dependency order and strict status transitions.
2. Implement `scripts/roadmap_realization_runner.py` CLI + importable functions for contract loading, schema validation, expansion trace validation, forbidden pattern scanning, entrypoint checks, behavioral test execution, and result artifact emission.
3. Add RF-02 and RF-03 contract instances under `artifacts/roadmap_contracts/` with required fields, dependency constraints, and initial `realization_status: planned_only`.
4. Add tests proving required fail-closed and success paths.
5. Run focused test suites and contract validation tests.

## Validation commands
1. `pytest tests/test_roadmap_realization_runner.py -q`
2. `pytest tests/test_roadmap_expansion_contracts.py -q`
