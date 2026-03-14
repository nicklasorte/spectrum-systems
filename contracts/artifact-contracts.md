# Artifact Contracts

Artifacts are the primary interface between Spectrum Systems engines. Every engine produces and consumes governed artifacts so that downstream workflows can rely on deterministic shapes, provenance, and auditability.

## Canonical contracts
- Canonical artifact contracts live in this repository under `contracts/`.
- Operational engines must import these contracts directly instead of redefining them locally.
- Contract identifiers, field names, and enumerations are part of the standards layer; do not rename or reorder them downstream.

## Change control
- Contract changes require an architecture review and publication through the standards manifest before downstream adoption.
- Engines must pin to a published `standards_version` (see `contracts/standards-manifest.json`) and may only advance after compatibility review.
- Non-breaking additions still require review; breaking changes demand a new schema version and migration notes.

## Referencing from operational engines
- Resolve schemas by `$id` or by path within this repo (e.g., `contracts/comment-resolution-matrix.schema.json`).
- Pin the contract version via tag or commit hash in build pipelines; do not vendor unchecked copies.
- Validate inputs and outputs against the canonical schema before emitting artifacts or accepting upstream artifacts.
- Surface the `standards_version` and `schema_version` in logs and manifests so orchestration layers can enforce compatibility.
