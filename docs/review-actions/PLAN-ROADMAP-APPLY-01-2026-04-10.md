# Plan — ROADMAP-APPLY-01 — 2026-04-10

## Prompt type
PLAN

## Roadmap item
ROADMAP-APPLY-01

## Objective
Apply the bounded adoption package via governed artifacts and bounded documentation updates, then emit review, delivery, and trace artifacts proving full lineage and fail-closed behavior.

## Declared files
List every file that will be created, modified, or deleted.
No other files may be changed during execution of this plan.

| File | Change type | Reason |
| --- | --- | --- |
| docs/roadmaps/execution_bundles.md | MODIFY | Apply PKG-REC-001 by requiring `evidence_link_map` for repair-adjacent slice completion and review handoff evidence. |
| docs/operational-evidence-standard.md | MODIFY | Apply PKG-CAND-002 by requiring `test_evidence_coverage_summary` at pre-umbrella decision checkpoints. |
| artifacts/rdx_runs/ROADMAP-APPLY-01-artifact-trace.json | CREATE | Emit canonical trace proving AEX→TLC→TPA→PQX→RQX→CDE→SEL lineage and bounded enforcement outcomes. |
| docs/reviews/RVW-ROADMAP-APPLY-01.md | CREATE | Emit mandatory governed review verdict for ownership, gating, execution, closure, and fail-closed integrity. |
| docs/reviews/ROADMAP-APPLY-01-DELIVERY-REPORT.md | CREATE | Emit mandatory delivery report with applied/rejected/deferred changes and final readiness state. |

## Contracts touched
None.

## Tests that must pass after execution
1. `python -m json.tool artifacts/rdx_runs/ROADMAP-APPLY-01-artifact-trace.json >/dev/null`
2. `git diff --check`

## Scope exclusions
- Do not alter roadmap sequencing authority in `docs/roadmaps/system_roadmap.md`.
- Do not introduce unbounded policy rewrites beyond PKG-REC-001 and PKG-CAND-002.
- Do not modify execution code paths or schemas in this cycle.

## Dependencies
- `ROADMAP-CLOSEOUT-01` must be complete.
- Input artifacts `bounded_adoption_package.ADOPT-02.json`, `adoption_readiness_record.ADOPT-03.json`, `program_roadmap_alignment_result.ALIGN-02.json`, and `adaptive_readiness_record.ADAPT-03.json` must remain `status: PASS`.
