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
| HI-3 | Enforce RE-05 checkpoint ordering: complete CL-01..CL-05 evidence, then execute NX-01..NX-03 only until Control Loop Closure Certification Gate passes. | Governance (spectrum-systems) | Open | spectrum-systems | CL-01..CL-05 evidence bundle + 3-slice trust-spine proof bundle | Transition policy blocks NX-04+ until certification artifact proves deterministic failure-to-policy enforcement and recurrence-prevention effect. |
| HI-4 | Preserve RE-04 evidence-chain references as adoption support during RE-06 reconciliation (candidate = input, RE-04 = validation, RE-05 = correction authority). | Governance (spectrum-systems) | Open | spectrum-systems | Canonical RE-04 and RE-05 artifacts | Roadmap authority surfaces explicitly retain RE-04/RE-05 support semantics without promoting candidate artifacts to authority status. |

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
