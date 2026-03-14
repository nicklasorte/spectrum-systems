# AGENTS.md

## Purpose
High-level guide for AI agents interacting with this repository and the broader czar ecosystem.

## Ecosystem overview
- system-factory: scaffolds new system repos from templates seeded by spectrum-systems governance.
- spectrum-systems: control plane for schemas, contracts, prompts, workflows, and standards manifests.
- operational engines: downstream system repos that implement the governed systems defined here.
- pipeline orchestration: spectrum-pipeline-engine aligns upstream artifacts, blocks schema drift, and emits run manifests.
- advisory outputs: spectrum-program-advisor consumes readiness bundles to produce briefs and readiness advisories.

## Agent roles
- Claude: architecture reasoning, design critiques, and review workflows.
- Codex: repository modifications and structured implementation of governance artifacts.
- Copilot: local coding assistance inside implementation repos.

## Design review culture
Architecture or contract changes should periodically trigger Claude-led design reviews before downstream adoption.

## Safe agent behavior
- Always read `docs/vision.md` before modifying structure.
- Treat schemas and contracts as authoritative; import contracts from spectrum-systems and do not redefine schemas locally.
- Do not generate automation code until workflows exist and lifecycle gates are satisfied.
- Prefer deterministic outputs; every system must define inputs, outputs, and evaluation tests.
- Research -> Plan -> Implement -> Test -> Review.
- Produce explicit instructions for repo modifications and honor governance standards.

## Navigation
- `CONTRACTS.md`
- `SYSTEMS.md`
- `docs/system-map.md`
- `docs/ecosystem-map.md`
- `contracts/standards-manifest.json`
