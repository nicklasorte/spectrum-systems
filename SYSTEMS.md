# Spectrum Systems Architecture Index

## Authority Note
- This file catalogs SYS-00x ecosystem engines and related assets.
- Canonical control-plane subsystem ownership (AEX/PQX/HNX/... and placeholder status) is authoritative only in `docs/architecture/system_registry.md`.
- If this file and the canonical registry diverge, the canonical registry wins.

- Start with `docs/system-map.md` and `docs/system-status-registry.md` for the current picture.
- Use `docs/ecosystem-map.md` for repo-level flows and control-plane coverage.
- Each system lives under `systems/<system>/` with `overview`, `interface`, `design`, `evaluation`, and `prompts` docs.
- Workflows live in `workflows/`; schemas in `schemas/`; evaluation assets in `eval/`.

## Core Principles
- Schema-led interfaces with deterministic outputs and explicit human review gates.
- Provenance and reproducibility metadata are required for every material artifact.
- Implementation code lives elsewhere; this repo defines interfaces, prompts, schemas, and evaluation plans.
- Artifact contracts live in `contracts/` and are the authoritative source for inputs/outputs shared across engines.
- **Runtime replay invariant:** All downstream runtime logic must operate exclusively on `replay_result` artifacts. No module may derive signals from pre-replay or non-governed data.

## System Catalog

| System | ID | Bottleneck | Key Docs | Schemas | Prompts | Eval |
| --- | --- | --- | --- | --- | --- | --- |
| Comment Resolution Engine | SYS-001 | BN-001 comment reconciliation and disposition drafting | systems/comment-resolution/overview.md; docs/comment-resolution-matrix-spreadsheet-contract.md (canonical spreadsheet contract) | schemas/comment-schema.json, schemas/issue-schema.json, schemas/provenance-schema.json | prompts/comment-resolution.md | eval/comment-resolution |
| Transcript-to-Issue Engine | SYS-002 | BN-002 untracked issues and actions in transcripts | systems/transcript-to-issue/overview.md | schemas/issue-schema.json, schemas/provenance-schema.json | prompts/transcript-to-issue.md | eval/transcript-to-issue |
| Study Artifact Generator | SYS-003 | BN-003 simulation output-to-report bottleneck | systems/study-artifact-generator/overview.md | schemas/study-output-schema.json, schemas/assumption-schema.json, schemas/provenance-schema.json | prompts/report-drafting.md | eval/study-artifacts |
| Spectrum Study Compiler | SYS-004 | BN-003 packaging and validation of study deliverables | systems/spectrum-study-compiler/overview.md | schemas/compiler-manifest.schema.json, schemas/artifact-bundle.schema.json, schemas/diagnostics.schema.json, schemas/study-output-schema.json, schemas/provenance-schema.json | prompts/spectrum-study-compiler.md, prompts/report-drafting.md (compiler-aware) | eval/spectrum-study-compiler |
| Spectrum Program Advisor | SYS-005 | BN-004 decision readiness clarity for program governance | systems/spectrum-program-advisor/overview.md | contracts/schemas/program_brief.schema.json, study_readiness_assessment.schema.json, next_best_action_memo.schema.json, decision_log.schema.json, risk_register.schema.json, assumption_register.schema.json, milestone_plan.schema.json | systems/spectrum-program-advisor/prompts.md | eval/spectrum-program-advisor |
| Meeting Minutes Engine | SYS-006 | BN-005 meeting output evaporation and unstructured minutes | systems/meeting-minutes-engine/overview.md; systems/meeting-minutes-engine/interface.md (contract-governed minutes) | contracts/meeting_minutes_contract.yaml | systems/meeting-minutes-engine/prompts.md | systems/meeting-minutes-engine/evaluation.md |
| Working Paper Review Engine | SYS-007 | BN-001 comment intake and normalization | systems/working-paper-review-engine/overview.md | contracts/examples/reviewer_comment_set.json, contracts/examples/comment_resolution_matrix_spreadsheet_contract.json, contracts/examples/working_paper_input.json | systems/working-paper-review-engine/prompts.md | systems/working-paper-review-engine/evaluation.md |
| DOCX Comment Injection Engine | SYS-008 | BN-001 anchored DOCX injection | systems/docx-comment-injection-engine/overview.md | contracts/examples/pdf_anchored_docx_comment_injection_contract.json, docs/comment-resolution-matrix-spreadsheet-contract.md | systems/docx-comment-injection-engine/prompts.md | systems/docx-comment-injection-engine/evaluation.md |
| Spectrum Pipeline Engine | SYS-009 | BN-006 orchestration gaps across engines | systems/spectrum-pipeline-engine/overview.md; workflows/spectrum-pipeline-engine.md | contracts/standards-manifest.json (meeting_minutes, meeting_agenda_contract, comment_resolution_matrix_spreadsheet_contract, readiness artifacts, external_artifact_manifest) | systems/spectrum-pipeline-engine/prompts.md | systems/spectrum-pipeline-engine/evaluation.md |

## Relationships
- Bottlenecks are defined in `docs/bottleneck-map.md`.
- Interfaces and standards: `docs/system-interface-spec.md`, `docs/system-philosophy.md`, `docs/system-lifecycle.md`.
- Traceability and reproducibility: `docs/data-provenance-standard.md`, `docs/reproducibility-standard.md`.
- Status and failure modes: `docs/system-status-registry.md`, `docs/system-failure-modes.md`.
- Contracts and schema versions: `CONTRACTS.md`, `CONTRACT_VERSIONING.md`, `contracts/standards-manifest.json`.
- Governance conformance: `docs/implementation-boundary.md`, `docs/governance-conformance-checklist.md`, `docs/ecosystem-map.md`.

## Contract Layer
- Spectrum Systems publishes canonical artifact contracts in `contracts/schemas/` with examples in `contracts/examples/`.
- Downstream repos (comment-resolution-engine, working-paper-review-engine, system-factory scaffolds) must import these schemas instead of redefining them.
- Contract versions and stability are tracked in `contracts/standards-manifest.json`; downstream consumers should pin to manifest versions.
- Changes follow the rules in `CONTRACT_VERSIONING.md` and must include provenance-ready metadata to align with `docs/data-provenance-standard.md`.
- The comment resolution matrix spreadsheet contract lives at `docs/comment-resolution-matrix-spreadsheet-contract.md` + `contracts/schemas/comment_resolution_matrix_spreadsheet_contract.schema.json`; `working-paper-review-engine` must emit it and `comment-resolution-engine` must consume/export it without renaming or reordering headers.
- The meeting agenda contract (`contracts/docs/meeting-agenda-contract.md`, schema in `contracts/schemas/meeting_agenda_contract.schema.json`) governs next-meeting agendas derived from prior minutes + resolution matrices; `spectrum-pipeline-engine` may orchestrate agenda generation across `meeting-minutes-engine` and `comment-resolution-engine`, emitting JSON/Markdown/DOCX outputs that preserve source references.
- `spectrum-pipeline-engine` orchestrates agenda and readiness bundles; it must consume pinned versions of meeting_minutes, meeting_agenda_contract, comment_resolution_matrix_spreadsheet_contract, readiness artifacts, and external_artifact_manifest without mutating upstream payloads.
- Meeting minutes artifacts must follow the canonical structure in `contracts/meeting_minutes_contract.yaml`; any operational engine that produces minutes needs to emit this exact shape.

## Implementation Guidance
- Keep schemas authoritative; update prompts and evaluations in lockstep with interface changes.
- Use `docs/repo-maintenance-checklist.md` to avoid drift and broken links.

## Meeting Minutes Artifact Contract
Operational engines that generate meeting minutes must emit outputs that conform exactly to `contracts/meeting_minutes_contract.yaml`. Transcripts are treated as input artifacts, and engines must transform them into structured minutes that match the contract without altering field names or nesting.

### Transcript Traceability
Meeting minutes artifacts should preserve traceability back to transcript timestamps and speakers whenever available so downstream consumers can verify source context.
