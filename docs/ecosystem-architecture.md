# Ecosystem Architecture

## Purpose
Explain how the czar repo organization is layered from scaffolding through advisory outputs so every repository knows where it fits and how governance flows.

## Architecture Layers
- **Layer 1 — System Factory**: generates and scaffolds new repositories with governance defaults and starter manifests so downstream repos begin aligned to `spectrum-systems`.
- **Layer 2 — Constitution (spectrum-systems)**: defines the rules, contracts, schemas, and workflows that govern the ecosystem. All contract changes originate here.
- **Layer 3 — Operational Engines**: implement the governed rules in production-facing systems. Examples: `working-paper-review-engine`, `comment-resolution-engine`, `meeting-minutes-engine`, `docx-comment-injection-engine`.
- **Layer 4 — Orchestration (spectrum-pipeline-engine)**: sequences operational engines, aligns contract versions, and emits pipeline run manifests and readiness bundles.
- **Layer 5 — Program Intelligence (spectrum-program-advisor)**: analyzes orchestrated artifacts and produces advisory outputs for program management decisions.

## Architecture Diagram
```mermaid
flowchart TB
    SF[system-factory]
    SS[spectrum-systems\n(constitution)]

    subgraph OE["operational engines"]
        WPR[working-paper-review-engine]
        CRE[comment-resolution-engine]
        MME[meeting-minutes-engine]
        DCI[docx-comment-injection-engine]
    end

    SPE[spectrum-pipeline-engine]
    SPA[spectrum-program-advisor]

    SF --> SS
    SS --> OE
    OE --> SPE
    SPE --> SPA
```

## Governance Flow
- Governance starts in `spectrum-systems`: contracts, schemas, and workflow standards are authored and versioned here.
- `system-factory` pulls the governance baseline to scaffold new repos, ensuring new engines and tools inherit current contracts and manifests.
- Operational engines implement the contracts they consume and emit governed artifacts that match the schemas defined in `spectrum-systems`.
- `spectrum-pipeline-engine` coordinates governed engines, enforces contract compatibility across a run, and publishes pipeline manifests that capture provenance and versions.
- `spectrum-program-advisor` consumes the governed bundles, applies program intelligence, and surfaces advisory outputs while staying pinned to the contract versions issued by the constitution.

## Artifact Envelope as the Interoperability Layer
- Engines exchange artifacts as **envelope + payload** pairs: the envelope standardizes `artifact_class`, `artifact_type`, `contract_version`, and lineage hooks; the payload remains the contract-defined schema.
- Raw DOCX transcripts are first-class artifacts: they enter with an envelope (`artifact_class=coordination`, `artifact_type=transcript`, `lifecycle_stage=raw`) even when no payload contract is attached yet.
- Shared envelope metadata reduces bespoke routing logic—pipelines can dispatch on envelope fields before touching payloads, and data lake sidecars mirror the envelope before considering payload contents.
- Pipeline and data lake components should reason over envelope fields first for routing, indexing, and compatibility, then apply payload-specific schema validation.
- See `docs/artifact-envelope-standard.md` and `contracts/schemas/artifact_envelope.schema.json` for the canonical envelope definition.

## Artifact Classes as the Core Ecosystem Abstraction
- The ecosystem is organized around three canonical artifact classes: coordination, work, and review (see `docs/artifact-classification-standard.md` and `contracts/artifact-class-registry.json`).
- Every engine declares which artifact classes it consumes and emits; manifests must include `artifact_class` alongside `artifact_type` to keep routing deterministic.
- Orchestration and advisory layers can reason over classes to simplify compatibility checks, reduce bespoke integrations, and enforce allowable transitions between classes.
- Class-aware manifests make it easier to swap implementations while preserving contract alignment across systems and pipelines.

## Meeting Minutes Artifact
- Meeting-minutes-engine ingests transcript text and emits a governed `meeting_minutes_record` JSON artifact.
- The JSON record is the source of truth that downstream engines consume before rendering DOCX outputs for stakeholders.
- The flow is: transcript input → `meeting_minutes_record` → DOCX export.

## Governance Manifest Enforcement
- Every governed repository publishes `.spectrum-governance.json` aligned to `governance/schemas/spectrum-governance.schema.json`.
- Manifests declare contract dependencies and pin versions to the canonical `contracts/standards-manifest.json`.
- CI validates manifests against the ecosystem registry and standards manifest, failing when systems or contracts are unknown.
- Manifests are the first enforcement layer that turns documented governance into executable checks across the ecosystem.

## Machine-Readable Ecosystem Dependency Graph
- Each downstream repo publishes `.spectrum-governance.json` aligned to `governance/schemas/spectrum-governance.schema.json`.
- Manifests are aggregated with `ecosystem/ecosystem-registry.json` to emit `artifacts/ecosystem-dependency-graph.json` (machine-readable) and `artifacts/ecosystem-dependency-graph.mmd` (Mermaid diagram).
- Contract pins in manifests must match `contracts/standards-manifest.json`, giving deterministic contract-to-system mappings.
- Upstream/downstream links in manifests capture system-to-system edges so orchestrators can reason about sequencing and impact analysis.
- The graph is regenerated in CI, keeping the registry, manifests, and visualization synchronized.

## Related References
- `docs/ecosystem-map.md`
- `docs/artifact-flow.md`
- `SYSTEMS.md`
