# Phase 5 — Hard Gates, Certification, A2A Guard

## Promotion hard gate
- Extended done certification to require CDE/BAX/CDE/CDE lineage refs on `active_runtime` authority path.
- Certification blocks when authority lineage is missing or not promotion-compatible.

## Certification input updates
- Added authority-lineage checks into done-certification check results.
- Added schema support for `tax_decision_ref`, `bax_decision_ref`, `cax_arbitration_ref`, and `cde_decision_ref`.

## A2A guard
- Added downstream intake guard in SEL runtime: `validate_downstream_a2a_consumption_guard(...)`.
- Guard blocks consumption when arbitration lineage is missing, BAX is freeze/block, CDE/CDE states are incompatible, or handoff policy denies.

> Registry alignment note: see docs/architecture/system_registry.md.
