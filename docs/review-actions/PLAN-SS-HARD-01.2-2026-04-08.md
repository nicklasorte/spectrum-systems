# Plan — SS-HARD-01.2 — 2026-04-08

## Prompt type
BUILD

## Roadmap item
SS-HARD-01.2 — Remaining governed-surface authority migration

## Objective
Migrate remaining governed producer/integration paths off legacy `gating_decision_artifact` execution inputs and ensure SEL-valid paths carry PQX authority proof artifacts end-to-end.

## Declared files
| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-SS-HARD-01.2-2026-04-08.md | CREATE | Required multi-file plan for focused migration slice. |
| scripts/run_harness_integrity_bundle.py | MODIFY | Migrate harness queue execution inputs from legacy gating artifact to canonical permission + PQX authority proof refs. |
| spectrum_systems/modules/runtime/system_end_to_end_validator.py | MODIFY | Ensure SEL valid-path context includes PQX authority proof artifact and expected execution identity fields. |
| tests/test_harness_integrity_bundle.py | MODIFY | Preserve deterministic bundle assertions while validating migrated authority path behavior. |
| tests/test_system_end_to_end_governed_loop.py | MODIFY | Validate SEL-valid governed path expectations after authority-proof migration. |

## Contracts touched
None.

## Tests that must pass after execution
1. `pytest tests/test_harness_integrity_bundle.py::test_run_bundle_emits_real_outputs_and_metrics -q`
2. `pytest tests/test_system_end_to_end_governed_loop.py::test_canonical_governed_scenario_passes_and_reports_successful_phases -q`
3. `pytest tests/test_system_end_to_end_governed_loop.py::test_required_artifacts_trace_lineage_and_sel_assertions_are_explicit -q`
4. `pytest tests/test_harness_integrity_bundle.py tests/test_system_end_to_end_governed_loop.py -q`

## Scope exclusions
- Do not reintroduce legacy execution authority acceptance in `execution_runner`.
- Do not alter queue-state execution semantics beyond migrating callers.
- Do not relax SEL PQX proof checks.
- Do not broaden into unrelated SS-HARD-02 workstreams.

## Dependencies
- Existing SS-HARD-01 canonical permission and PQX authority validation paths remain source-of-truth.
