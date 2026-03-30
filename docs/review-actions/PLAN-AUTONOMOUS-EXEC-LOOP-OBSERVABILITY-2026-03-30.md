# Plan — CTRL-LOOP-01-OBS — 2026-03-30

## Prompt type
PLAN

## Roadmap item
CTRL-LOOP-01

## Objective
Add deterministic repo-native cycle status/observability reporting (status artifacts, blocked-reason normalization, backlog aggregation, and phase metrics) over existing cycle manifests and linked artifacts without introducing new control-plane architecture.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| contracts/schemas/cycle_status_artifact.schema.json | CREATE | Contract-first status artifact schema for single-cycle observability output |
| contracts/schemas/cycle_backlog_snapshot.schema.json | CREATE | Contract for multi-cycle queue/backlog + metrics aggregation snapshot |
| contracts/examples/cycle_status_artifact.json | CREATE | Golden-path example for single-cycle status output |
| contracts/examples/cycle_backlog_snapshot.json | CREATE | Golden-path example for aggregated backlog/metrics output |
| contracts/standards-manifest.json | MODIFY | Publish version pins/metadata for new observability contracts |
| spectrum_systems/orchestration/cycle_observability.py | CREATE | Deterministic status builder + blocked reason normalization + aggregation/rollups |
| spectrum_systems/orchestration/__init__.py | MODIFY | Export observability entrypoints |
| scripts/run_cycle_observability.py | CREATE | Repo-native CLI seam for status/aggregation output artifacts |
| tests/fixtures/autonomous_cycle/cycle_status_blocked_manifest.json | CREATE | Fixture for normalized blocked-reason behavior |
| tests/test_cycle_observability.py | CREATE | Integration tests for status, aggregation, metrics, and fail-closed behavior |
| docs/architecture/autonomous_execution_loop.md | MODIFY | Document status artifact, blocked categories, backlog visibility, and metric derivation |
| docs/runbooks/cycle_runner.md | MODIFY | Add runbook section for status/aggregation generation and fail-closed expectations |
| docs/roadmap/system_roadmap.md | MODIFY | Update compatibility roadmap row notes for observability/status extension |
| docs/roadmaps/system_roadmap.md | MODIFY | Update authoritative roadmap row notes for observability/status extension |
| docs/reviews/autonomous_execution_cycle_observability_slice_report.md | CREATE | Repo-native completion/review artifact for this grouped PQX slice |

## Contracts touched
- `cycle_status_artifact` (new)
- `cycle_backlog_snapshot` (new)
- `contracts/standards-manifest.json` (new contract version metadata)

## Tests that must pass after execution
1. `pytest tests/test_cycle_observability.py`
2. `pytest tests/test_cycle_runner.py`
3. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`

## Scope exclusions
- Do not redesign cycle runner state machine semantics.
- Do not add external service/storage dependencies; keep observability artifact-first and repo-native.
- Do not alter PQX execution adapter behavior beyond read-only observability consumption.

## Dependencies
- `PLAN-AUTONOMOUS-EXEC-LOOP-2026-03-30.md`
- `PLAN-AUTONOMOUS-EXEC-LOOP-CLOSED-2026-03-30.md`
- `PLAN-AUTONOMOUS-EXEC-LOOP-REVIEW-FIX-REENTRY-2026-03-30.md`
