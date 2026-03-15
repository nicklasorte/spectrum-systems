# Ecosystem operating model

Status: Accepted

Date: 2026-03-15

## Context
The ecosystem needed a stable architecture that keeps artifact creation and evaluation in sync while allowing downstream engines to specialize. Without a defined operating model, systems risked drifting, duplicating governance logic, and losing provenance across research, drafting, review, and adjudication.

## Decision
Adopt a two-loop architecture that separates but links the **artifact production loop** and the **artifact evaluation loop**. Production handles tasking, drafting, review, adjudication, and updated artifacts. Evaluation ingests outputs and evidence bundles to validate contracts, maturity claims, and roadmap alignment. The bridge between loops is governed artifacts (contracts, schemas, registries) plus correlated run evidence.

## Consequences
- Each system must declare which loop(s) it serves and publish inputs/outputs aligned to governed contracts.
- Registry files (system registry, dependency graph, roadmap tracker) and design reviews must map systems to the two-loop model to prevent architectural drift.
- Pipelines and standards (provenance, evaluation, review evidence) enforce consistent handoffs between production and evaluation.
- Coordination between loops relies on correlated run evidence to keep decisions auditable and reproducible.

## Alternatives considered
- A single monolithic pipeline that blends production and evaluation, which would obscure ownership and make governance brittle.
- Per-system bespoke workflows without a shared loop model, which would fragment standards and make cross-system validation impossible.
- Informal guidance without explicit loops, which would fail to anchor registries, contracts, and review expectations.

## Related artifacts
- `docs/spectrum-study-operating-model.md`
- `docs/ecosystem-architecture.md`
- `docs/system-architecture.md`
- `docs/system-map.md`
- `docs/run-evidence-correlation-rule.md`
- `docs/design-review-standard.md`
