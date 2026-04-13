# Ecosystem Architecture

## Purpose
Explain how the czar repo organization is layered from scaffolding through advisory outputs so every repository knows where it fits and how governance flows.

## Architecture Layers
- **Layer 1 — System Factory**: generates and scaffolds new repositories with governance defaults and starter manifests so downstream repos begin aligned to `spectrum-systems`.
- **Layer 2 — Constitution (spectrum-systems)**: defines the rules, contracts, schemas, and workflows that govern the ecosystem. All contract changes originate here.
- **Layer 3 — Operational Engines**: implement the governed rules in production-facing systems. Examples: `working-paper-review-engine`, `comment-resolution-engine`, `meeting-minutes-engine`, `docx-comment-injection-engine`.
- **Layer 4 — Orchestration (spectrum-pipeline-engine)**: sequences operational engines, aligns contract versions, and emits pipeline run manifests and readiness bundles.
- **Layer 5 — Program Intelligence (spectrum-program-advisor)**: analyzes orchestrated artifacts and produces advisory outputs for program management decisions.

## Operating Model: Two Interacting Loops
- **Coordination Loop** moves roster → meetings → transcript → minutes → action items/FAQ → agenda/slides → next meeting and emits **Engineering Tasks** to the work queue; `meeting-minutes-engine` anchors this loop.
- **Document Production Loop** runs **Engineering Tasks** → **Engineering Outputs** → working paper → compare with previous revision → updated working paper → agency review → reviewer comments → comment resolution matrix → adjudicated matrix → updated paper; engines like `working-paper-review-engine`, `comment-resolution-engine`, and `docx-comment-injection-engine` live here.
- **Bridge** separates **Engineering Tasks** (from action items, study plan, schedule, open questions) and **Engineering Outputs** (figures, tables, analysis artifacts, working paper revisions) so the loops hand off cleanly.
- Orchestration (`spectrum-pipeline-engine`) and program intelligence (`spectrum-program-advisor`) span the loops to keep sequencing, provenance, and readiness aligned.
- See `docs/spectrum-study-operating-model.md` for the canonical operating model and ASCII loop diagram.

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

## Local Governance Artifact Rule
The ecosystem assumes governance artifacts are part of the platform control plane and are always locally available to engines and orchestration. Schemas, contracts, standards manifests, and registry files must be mounted or vendored from the `spectrum-systems` checkout rather than fetched over the network at runtime.

## System Registry Surfaces and Authority
- Canonical authority for subsystem names, acronyms, ownership, and placeholder status is `docs/architecture/system_registry.md`.
- `docs/system-registry.md` is a companion ecosystem inventory summary and must defer ownership authority to the canonical registry.
- `docs/systems-registry.md` is a compatibility companion stub for legacy links.
- `ecosystem/system-registry.json` remains the machine-readable ecosystem inventory used by automation.
- Future dependency graphing, compliance checks, and advisor capabilities should consume the machine-readable inventory while resolving ownership authority from the canonical registry.

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

## Ecosystem Dependency Graph
- The dependency graph is the structural map of the ecosystem—every system, contract, artifact type, and loop alignment is represented so orchestration and governance stay legible.
- Future governance, impact analysis, and maturity reviews should rely on `ecosystem/dependency-graph.json` (generated by `scripts/build_dependency_graph.py`), which is documented in `docs/ecosystem-dependency-graph.md` and validated by `ecosystem/dependency-graph.schema.json`.
- Explicit edges prevent hidden dependencies and repo sprawl: changing a contract or artifact shows immediately which systems, loops, and downstream outputs are affected.
- Summary and visualization outputs live in `artifacts/dependency-graph-summary.md` and `artifacts/dependency-graph.mmd` to give humans a stable view of the control-plane map.

## Related References
- `docs/ecosystem-map.md`
- `docs/artifact-flow.md`
- `SYSTEMS.md`
