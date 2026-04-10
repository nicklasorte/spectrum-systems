# PLAN-EVAL-DRIFT-SLICE-CONTROL-01-2026-04-10

## Prompt type
BUILD

## Scope
Implement `EVAL-DRIFT-SLICE-CONTROL-01` as an artifact-first, fail-closed, serial run across four umbrellas:
1. `EVALUATION_LAYER`
2. `DRIFT_LAYER`
3. `SLICE_IMPROVEMENT_LAYER`
4. `CONTROL_PREP_LAYER`

## Canonical alignment checks
- Align role ownership and authority boundaries to `README.md` and `docs/architecture/system_registry.md`.
- Keep CDE/TPA/PQX/SEL inactive as authority systems in this run.
- Emit only interpretation, recommendation, prioritization, and preparation artifacts.
- Preserve strict serial ordering; stop on any fail-closed trigger.

## Planned file changes
1. **Create** `artifacts/rdx_runs/EVAL-DRIFT-SLICE-CONTROL-01-artifact-trace.json`
   - Canonical serial execution trace with umbrella-by-umbrella decisions and stop conditions.
2. **Create** `artifacts/rdx_runs/EVAL-DRIFT-SLICE-CONTROL-01/*.json`
   - Per-slice and per-umbrella artifacts for evaluation, drift, slice improvement, and control preparation.
3. **Create** `docs/reviews/RVW-EVAL-DRIFT-SLICE-CONTROL-01.md`
   - Mandatory governance review with one of the required verdicts.
4. **Create** `docs/reviews/EVAL-DRIFT-SLICE-CONTROL-01-DELIVERY-REPORT.md`
   - Delivery report covering emitted artifacts, readiness, failures, and exact next cycle.

## Validation plan
- Validate JSON syntax and deterministic structure for all emitted run artifacts.
- Verify serial umbrella ordering and `umbrella_decision_artifact` presence.
- Verify no forbidden authority decision artifacts are emitted.
- Verify control-prep outputs are explicitly non-authoritative and bounded.
