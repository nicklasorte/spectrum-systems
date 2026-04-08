# Plan — BATCH-AEX-FIX-01 — 2026-04-08

## Prompt type
BUILD

## Roadmap item
BATCH-AEX-FIX-01

## Objective
Close the cycle runner repo-write bypass to PQX, harden mutation-intent inference, and add structural/behavioral tests so repo-write execution is fail-closed behind AEX admission lineage.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| spectrum_systems/orchestration/pqx_handoff_adapter.py | MODIFY | Enforce admission lineage at cycle runner → handoff seam before run_pqx_slice for repo-write requests |
| spectrum_systems/modules/runtime/top_level_conductor.py | MODIFY | Fail-closed mutation intent inference and consolidate duplicate repo-write guard |
| spectrum_systems/aex/engine.py | MODIFY | Replace hardcoded rejection created_at with dynamic runtime timestamp |
| tests/test_aex_repo_write_boundary_structural.py | MODIFY | Extend structural boundary checks to include direct run_pqx_slice caller allowlist |
| tests/test_pqx_handoff_adapter.py | MODIFY | Add tests for cycle-runner handoff repo-write admission fail-closed/success behaviors |
| tests/test_cycle_runner.py | MODIFY | Add cycle runner tests proving repo-write handoff blocks without lineage and passes with lineage |
| tests/test_aex_fail_closed.py | MODIFY | Assert rejection created_at is dynamic runtime timestamp |
| tests/test_top_level_conductor.py | MODIFY | Add explicit non-mutating declaration for requests to satisfy fail-closed inference |
| tests/test_system_handoff_integrity.py | MODIFY | Add explicit non-mutating declaration for requests to satisfy fail-closed inference |
| tests/test_roadmap_signal_generation.py | MODIFY | Add explicit non-mutating declaration for requests to satisfy fail-closed inference |
| tests/test_failure_learning_artifacts.py | MODIFY | Add explicit non-mutating declaration for requests to satisfy fail-closed inference |
| tests/test_pre_pr_repair_loop.py | MODIFY | Add explicit non-mutating declaration for requests to satisfy fail-closed inference |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_pqx_handoff_adapter.py tests/test_cycle_runner.py tests/test_aex_repo_write_boundary_structural.py tests/test_aex_fail_closed.py tests/test_tlc_requires_admission_for_repo_write.py tests/test_tlc_handoff_flow.py`
2. `pytest tests/test_top_level_conductor.py tests/test_system_handoff_integrity.py tests/test_roadmap_signal_generation.py tests/test_failure_learning_artifacts.py tests/test_pre_pr_repair_loop.py`

## Scope exclusions
- Do not redesign AEX, TLC, cycle runner orchestration model, or PQX architecture.
- Do not add new subsystems or contracts.
- Do not broaden enforcement beyond the specified repo-write seams.

## Dependencies
- None.
