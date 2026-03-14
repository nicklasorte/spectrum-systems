# Spectrum Systems Architecture Index

## How to Navigate
- Start with `docs/system-map.md` and `docs/system-status-registry.md` for the current picture.
- Each system lives under `systems/<system>/` with `overview`, `interface`, `design`, `evaluation`, and `prompts` docs.
- Workflows live in `workflows/`; schemas in `schemas/`; evaluation assets in `eval/`.

## Core Principles
- Schema-led interfaces with deterministic outputs and explicit human review gates.
- Provenance and reproducibility metadata are required for every material artifact.
- Implementation code lives elsewhere; this repo defines interfaces, prompts, schemas, and evaluation plans.
- Artifact contracts live in `contracts/` and are the authoritative source for inputs/outputs shared across engines.

## System Catalog

| System | ID | Bottleneck | Key Docs | Schemas | Prompts | Eval |
| --- | --- | --- | --- | --- | --- | --- |
| Comment Resolution Engine | SYS-001 | BN-001 comment reconciliation and disposition drafting | systems/comment-resolution/overview.md; docs/comment-resolution-matrix-spreadsheet-contract.md (canonical spreadsheet contract) | schemas/comment-schema.json, schemas/issue-schema.json, schemas/provenance-schema.json | prompts/comment-resolution.md | eval/comment-resolution |
| Transcript-to-Issue Engine | SYS-002 | BN-002 untracked issues and actions in transcripts | systems/transcript-to-issue/overview.md | schemas/issue-schema.json, schemas/provenance-schema.json | prompts/transcript-to-issue.md | eval/transcript-to-issue |
| Study Artifact Generator | SYS-003 | BN-003 simulation output-to-report bottleneck | systems/study-artifact-generator/overview.md | schemas/study-output-schema.json, schemas/assumption-schema.json, schemas/provenance-schema.json | prompts/report-drafting.md | eval/study-artifacts |
| Spectrum Study Compiler | SYS-004 | BN-003 packaging and validation of study deliverables | systems/spectrum-study-compiler/overview.md | schemas/compiler-manifest.schema.json, schemas/artifact-bundle.schema.json, schemas/diagnostics.schema.json, schemas/study-output-schema.json, schemas/provenance-schema.json | prompts/spectrum-study-compiler.md, prompts/report-drafting.md (compiler-aware) | eval/spectrum-study-compiler |

## Relationships
- Bottlenecks are defined in `docs/bottleneck-map.md`.
- Interfaces and standards: `docs/system-interface-spec.md`, `docs/system-philosophy.md`, `docs/system-lifecycle.md`.
- Traceability and reproducibility: `docs/data-provenance-standard.md`, `docs/reproducibility-standard.md`.
- Status and failure modes: `docs/system-status-registry.md`, `docs/system-failure-modes.md`.
- Contracts and schema versions: `CONTRACTS.md`, `CONTRACT_VERSIONING.md`, `contracts/standards-manifest.json`.

## Contract Layer
- Spectrum Systems publishes canonical artifact contracts in `contracts/schemas/` with examples in `contracts/examples/`.
- Downstream repos (comment-resolution-engine, working-paper-review-engine, system-factory scaffolds) must import these schemas instead of redefining them.
- Contract versions and stability are tracked in `contracts/standards-manifest.json`; downstream consumers should pin to manifest versions.
- Changes follow the rules in `CONTRACT_VERSIONING.md` and must include provenance-ready metadata to align with `docs/data-provenance-standard.md`.
- The comment resolution matrix spreadsheet contract lives at `docs/comment-resolution-matrix-spreadsheet-contract.md` + `contracts/schemas/comment_resolution_matrix_spreadsheet_contract.schema.json`; `working-paper-review-engine` must emit it and `comment-resolution-engine` must consume/export it without renaming or reordering headers.

## Implementation Guidance
- Keep schemas authoritative; update prompts and evaluations in lockstep with interface changes.
- Use `docs/repo-maintenance-checklist.md` to avoid drift and broken links.
