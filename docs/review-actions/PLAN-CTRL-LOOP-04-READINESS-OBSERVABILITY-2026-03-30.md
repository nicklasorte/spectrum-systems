# Plan — CTRL-LOOP-04 Readiness Observability — 2026-03-30

## Prompt type
PLAN

## Roadmap item
CTRL-LOOP-04 — Remediation closure readiness + progression reinstatement readiness observability

## Objective
Add deterministic, artifact-derived observability artifacts and backlog rollups that explain remediation/reinstatement readiness and blocking causes without changing enforcement authority boundaries.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CTRL-LOOP-04-READINESS-OBSERVABILITY-2026-03-30.md | CREATE | Required plan-first execution record for grouped multi-file PQX slice |
| PLANS.md | MODIFY | Register newly created active plan entry |
| contracts/schemas/judgment_remediation_readiness_status.schema.json | CREATE | New governed remediation readiness observability contract |
| contracts/schemas/judgment_reinstatement_readiness_status.schema.json | CREATE | New governed reinstatement readiness observability contract |
| contracts/examples/judgment_remediation_readiness_status.json | CREATE | Golden-path example for remediation readiness status |
| contracts/examples/judgment_reinstatement_readiness_status.json | CREATE | Golden-path example for reinstatement readiness status |
| contracts/schemas/cycle_backlog_snapshot.schema.json | MODIFY | Extend backlog queues/metrics for remediation/reinstatement visibility |
| contracts/examples/cycle_backlog_snapshot.json | MODIFY | Keep example aligned with backlog schema extensions |
| contracts/standards-manifest.json | MODIFY | Register new contracts and version bump |
| spectrum_systems/orchestration/cycle_observability.py | MODIFY | Add deterministic readiness builders and backlog integration |
| spectrum_systems/orchestration/__init__.py | MODIFY | Export new observability builders |
| tests/test_cycle_observability.py | MODIFY | Add readiness and backlog integration/fail-closed deterministic tests |
| tests/test_contracts.py | MODIFY | Add schema/example validation coverage for new readiness contracts |
| docs/architecture/autonomous_execution_loop.md | MODIFY | Document readiness semantics, computation, blocking reasons, and operator value |
| docs/roadmaps/system_roadmap.md | MODIFY | Update authoritative roadmap status with CTRL-LOOP-04 observability slice |
| docs/roadmap/system_roadmap.md | MODIFY | Update operational compatibility mirror in lockstep |

## Contracts touched
- `judgment_remediation_readiness_status` (new)
- `judgment_reinstatement_readiness_status` (new)
- `cycle_backlog_snapshot` (additive observability extension)
- `standards_manifest` version and contract registry entries

## Tests that must pass after execution
1. `pytest tests/test_cycle_observability.py tests/test_judgment_enforcement.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/verify-changed-scope/run.sh`

## Scope exclusions
- Do not change enforcement/control decision authority semantics.
- Do not introduce any automatic state mutation from readiness artifacts.
- Do not create a parallel observability/reporting subsystem.
- Do not modify unrelated queue/runtime modules.

## Dependencies
- CTRL-LOOP-03 remediation closure + reinstatement governance must be complete.
- Existing cycle observability and backlog snapshot seams must remain authoritative extension points.
