# Roadmap Generation Delivery — Action Tracker

- **Source Review:** `docs/reviews/2026-03-31-roadmap-generation-delivery-report.md`
- **Owner:** Spectrum Systems Engineering
- **Last Updated:** 2026-03-31

## Critical Items

| ID | Action Item | Owner | Status | Target Repo | Blocking Dependencies | Acceptance Criteria |
| --- | --- | --- | --- | --- | --- | --- |
| CR-1 | Keep active authority (`docs/roadmaps/system_roadmap.md`) and compatibility mirror (`docs/roadmap/system_roadmap.md`) reconciled in the same change set for roadmap-surface edits. | Governance (spectrum-systems) | Resolved | spectrum-systems | None | `tests/test_roadmap_authority.py` and `python scripts/check_roadmap_authority.py` pass after each roadmap-surface update. |

## High-Priority Items

| ID | Action Item | Owner | Status | Target Repo | Blocking Dependencies | Acceptance Criteria |
| --- | --- | --- | --- | --- | --- | --- |
| HI-1 | Continue source-authority hardening by promoting ingestion-only obligations to runtime/certification-grade obligations as structured source depth improves. | Governance (spectrum-systems) | Open | spectrum-systems | Source artifact depth increase | New obligations are added to `docs/source_structured/*.json` and reflected by `docs/source_indexes/obligation_index.json` without schema/index validation failures. |
| HI-2 | Preserve Control Loop Closure Gate-first sequencing; do not claim true closed-loop MVP until CL-01..CL-05 evidence is complete. | Governance (spectrum-systems) | Open | spectrum-systems | None | Roadmap updates keep CL-01..CL-05 as pre-expansion hard gate and do not assert true closed-loop MVP before evidence-backed completion. |

## Medium-Priority Items

| ID | Action Item | Owner | Status | Target Repo | Blocking Dependencies | Acceptance Criteria |
| --- | --- | --- | --- | --- | --- | --- |
| MI-1 | Re-run source index refresh (`scripts/build_source_indexes.py`) during each roadmap-generation pass and record no-diff vs changed-diff outcomes in delivery artifacts. | Governance (spectrum-systems) | Open | spectrum-systems | None | Each roadmap-generation delivery artifact explicitly records source index refresh outcome and validation status. |

## Low-Priority Items

None.

## Blocking Items

- HI-2 blocks any roadmap status change to “true closed-loop MVP” until CL-01..CL-05 completion is demonstrated with governed artifacts.

## Deferred Items

- Deep source-obligation extraction from missing raw source files is deferred until those raw artifacts are available in governed scope.
