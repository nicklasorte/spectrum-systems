# Plan — Autonomous Loop Review→Fix Re-entry Bundle — 2026-03-30

## Prompt type
PLAN

## Roadmap item
CTRL-LOOP-01 (grouped PQX review/fix re-entry slice)

## Objective
Extend the existing closed-loop autonomous cycle so schema-valid review artifacts are ingested live, fix-roadmaps are auto-generated, approved fix groups re-enter PQX through existing seams, and deterministic fail-closed transitions progress through the review-driven fix loop.

## Declared files

| File | Change type | Reason |
| --- | --- | --- |
| docs/review-actions/PLAN-AUTONOMOUS-EXEC-LOOP-REVIEW-FIX-REENTRY-2026-03-30.md | CREATE | Required multi-file plan before grouped BUILD slice |
| PLANS.md | MODIFY | Register active grouped PQX slice plan |
| spectrum_systems/orchestration/cycle_runner.py | MODIFY | Add review ingestion validation, fix-roadmap auto-trigger, and PQX fix re-entry transitions |
| contracts/schemas/cycle_manifest.schema.json | MODIFY | Add manifest fields needed for deterministic review/fix loop orchestration |
| contracts/examples/cycle_manifest.json | MODIFY | Keep golden-path cycle manifest aligned with schema and new fields |
| contracts/standards-manifest.json | MODIFY | Publish updated cycle_manifest contract version metadata |
| tests/test_cycle_runner.py | MODIFY | Add end-to-end review-driven re-entry happy/blocked/replay coverage |
| docs/architecture/autonomous_execution_loop.md | MODIFY | Document review ingestion, auto-triggered fix roadmap generation, and re-entry loop semantics |
| docs/runbooks/cycle_runner.md | MODIFY | Operator runbook updates for review/fix loop gates and blocked behavior |
| docs/roadmap/system_roadmap.md | MODIFY | Keep compatibility mirror aligned with expanded CTRL-LOOP-01 behavior |
| docs/reviews/autonomous_execution_review_fix_reentry_slice_report.md | CREATE | Repo-native completion/status artifact for this grouped slice |

## Contracts touched
- `cycle_manifest` (additive schema extension for fix-loop orchestration)
- `contracts/standards-manifest.json` (version metadata update for `cycle_manifest`)

## Tests that must pass after execution
1. `pytest tests/test_cycle_runner.py`
2. `pytest tests/test_contracts.py`
3. `pytest tests/test_module_architecture.py`
4. `python scripts/run_contract_enforcement.py`

## Scope exclusions
- Do not redesign control-plane architecture or introduce a parallel orchestrator.
- Do not reimplement PQX runtime internals; use the existing `pqx_handoff_adapter` seam.
- Do not reimplement GOV-10 certification internals; keep certification seam invocation unchanged.
- Do not alter unrelated roadmap rows or non-cycle orchestration components.

## Dependencies
- `docs/review-actions/PLAN-AUTONOMOUS-EXEC-LOOP-CLOSED-2026-03-30.md` merged foundation remains baseline.
- Existing seams remain authoritative:
  - `spectrum_systems.orchestration.pqx_handoff_adapter.handoff_to_pqx`
  - `spectrum_systems.fix_engine.generate_fix_roadmap.generate_fix_roadmap`
  - `spectrum_systems.modules.governance.done_certification.run_done_certification`
