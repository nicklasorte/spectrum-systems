# Plan — CTRL-LOOP-03-STRATEGY-SOURCE-AUTHORITY — 2026-03-30

## Prompt type
PLAN

## Roadmap item
Grouped PQX slice — strategy/source authority wired into cycle manifest, roadmap provenance, progression hard gates, and downstream traceability.

## Objective
Require deterministic strategy/source authority at cycle entry, carry machine-readable provenance through roadmap/progression artifacts, and fail closed when authority/provenance is missing.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-CTRL-LOOP-03-STRATEGY-SOURCE-AUTHORITY-2026-03-30.md | CREATE | Required PLAN artifact before grouped multi-file governance wiring |
| PLANS.md | MODIFY | Register plan in active plans table |
| contracts/schemas/cycle_manifest.schema.json | MODIFY | Add explicit strategy/source authority fields and fail-closed manifest constraints |
| contracts/examples/cycle_manifest.json | MODIFY | Keep golden-path example aligned with new manifest governance fields |
| contracts/schemas/roadmap_review_artifact.schema.json | MODIFY | Add machine-readable strategy/source provenance block and invariants linkage |
| contracts/examples/roadmap_review_artifact.json | MODIFY | Golden-path example with provenance fields populated |
| spectrum_systems/orchestration/cycle_runner.py | MODIFY | Enforce strategy/source authority and roadmap provenance hard gates in governed progression |
| tests/test_cycle_runner.py | MODIFY | Add end-to-end fail-closed governance tests including deterministic repeated behavior |
| docs/architecture/autonomous_execution_loop.md | MODIFY | Document where strategy/source authority and provenance are now enforced |
| docs/roadmaps/system_roadmap.md | MODIFY | Record grouped PQX slice completion in authoritative roadmap |
| contracts/standards-manifest.json | MODIFY | Version bumps and contract notes for modified schemas |

## Contracts touched
- `cycle_manifest` (schema + example + standards manifest version update)
- `roadmap_review_artifact` (schema + example + standards manifest version update)

## Tests that must pass after execution
1. `pytest tests/test_cycle_runner.py`
2. `pytest tests/test_contracts.py tests/test_contract_enforcement.py`
3. `python scripts/run_contract_enforcement.py`
4. `.codex/skills/contract-boundary-audit/run.sh`
5. `.codex/skills/verify-changed-scope/run.sh docs/review-actions/PLAN-CTRL-LOOP-03-STRATEGY-SOURCE-AUTHORITY-2026-03-30.md`

## Scope exclusions
- Do not create a parallel governance subsystem.
- Do not redesign state-machine phases or runtime/control role boundaries.
- Do not modify review_orchestrator interfaces outside existing strategy/source semantics.

## Dependencies
- Existing autonomous execution loop seams in `cycle_manifest`, `roadmap_review_artifact`, and `cycle_runner` must remain primary integration surfaces.
- `docs/architecture/system_strategy.md` and `docs/architecture/system_source_index.md` remain canonical strategy/source references.
