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

## Related References
- `docs/ecosystem-map.md`
- `docs/artifact-flow.md`
- `SYSTEMS.md`
