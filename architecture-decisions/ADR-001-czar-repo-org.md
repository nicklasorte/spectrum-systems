# Czar repository responsibilities: system-factory → spectrum-systems → operational engines

Date: 2026-03-14  
Status: Accepted

## Context

The czar ecosystem spans repo types with different ownership and lifecycle expectations. System scaffolding, governance control-plane artifacts, and runnable engines need clear separation to prevent schema drift, preserve provenance, and allow downstream teams to iterate independently. Design reviews highlighted repeated confusion about where contracts live versus where pipelines execute.

## Decision

Adopt a three-tier repository pattern:
- **system-factory** — scaffolds new system repos from governance templates and enforces baseline contracts, prompts, and workflows.
- **spectrum-systems** — control plane for schemas, contracts, prompts, workflows, standards manifests, and design artifacts; authoritative source for governed interfaces.
- **operational engines** — downstream system repos that implement governed systems, ingest updates from `spectrum-systems`, and emit artifacts per contracts/schemas.

## Alternatives Considered

- Single monorepo for governance and engines — rejected due to upgrade risk, unclear ownership boundaries, and harder provenance controls.
- Per-system repos without a control-plane hub — rejected because contracts and schemas would fragment, increasing schema drift and duplicated governance.
- Document-only coordination (no scaffolding) — rejected; lacks deterministic scaffolding and reproducible adoption of standards.

## Consequences

- Clear accountability: governance artifacts stay in `spectrum-systems`, while execution stays in operational engines.
- Controlled evolution: updates flow from `system-factory` templates and `spectrum-systems` manifests into engines via pipelines, reducing drift.
- Coordination overhead: requires release notes and pipeline orchestration to propagate contract changes safely across repos.
