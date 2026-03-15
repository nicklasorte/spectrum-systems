# Ecosystem Dependency Graph

The dependency graph is the machine-readable map of the Spectrum Systems ecosystem. It captures how repositories, engines, governed artifacts, and contracts relate so the control plane can see coupling, run impact analysis, and stop hidden dependencies from forming as new engines are added.

## Purpose
- Make every ecosystem dependency explicit: which repos exist, what they consume and emit, and which contracts they rely on.
- Provide a structural view that governance, orchestration, and advisors can query to reason about contract changes, artifact flows, and maturity.
- Prevent mystery dependencies and drift between registries, manifests, and downstream engines.
- Serve as the backbone for future maturity evaluations, policy enforcement, and pipeline/advisor reasoning.

## Questions the graph must answer
- What repositories belong to the ecosystem and how are they aligned to the loops?
- Which artifact types flow between engines and which systems produce or consume them?
- Which contracts are consumed and emitted, and who the intended consumers are?
- Which systems participate in the coordination loop, document-production loop, or cross-loop orchestration/advisory roles?
- What breaks if a contract or artifact changes, and which edges are impacted?

## Location and generation
- Machine-readable graph: `ecosystem/dependency-graph.json` (validated by `ecosystem/dependency-graph.schema.json`).
- Human-readable summary: `artifacts/dependency-graph-summary.md`.
- Visualization: `artifacts/dependency-graph.mmd`.
- Generator: `scripts/build_dependency_graph.py` (pulls from `ecosystem/system-registry.json`, `contracts/standards-manifest.json`, and `contracts/artifact-class-registry.json`, with deterministic ordering and documented manual annotations where needed).

Keep this document and the graph in lockstep: every new repo, contract, or artifact type should update the registry, rerun the generator, and review the resulting graph for accuracy.***
