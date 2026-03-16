# Artifact Contracts

Spectrum Systems is the authoritative source for machine-readable artifact contracts that downstream implementation repos must consume. Contracts define the canonical input/output structures, required provenance metadata, and compatibility guarantees for spectrum engineering workflows.

## Schema authority
`contracts/schemas/` is the **canonical source** for all governed artifact contract schemas. Downstream repos must import schemas from this directory and pin versions against `contracts/standards-manifest.json`. Root `schemas/` contains supplemental structural schemas (comment, issue, provenance, etc.) that are not governed artifact contracts. See `schemas/README.md` for the full schema authority statement and import rules.

## Why contracts live here
- This repo is the governing czar for the ecosystem; contracts must be published here before system-factory scaffolds them elsewhere.
- Downstream engines (e.g., Comment Resolution Engine, Working Paper Review Engine) import these contracts instead of redefining them.
- Changes to contracts follow the policies in `CONTRACT_VERSIONING.md` and are published through `contracts/standards-manifest.json`.

## How to consume contracts
- Use the JSON Schemas in `contracts/schemas/` as the single source of truth.
- Pull example payloads from `contracts/examples/` for fixtures and integration tests.
- Load schemas programmatically via `spectrum_systems.contracts.load_schema` and validate instances with `validate_artifact`.
- Track the standards release in `contracts/standards-manifest.json`; do not fork schema definitions in downstream repos.

## Envelope + payload interoperability
- Contract schemas define the payload structure; the artifact envelope standard (`docs/artifact-envelope-standard.md`, `contracts/schemas/artifact_envelope.schema.json`) defines the outer interoperability metadata.
- Engines should emit payloads wrapped in the envelope so orchestration and data lake layers can route by `artifact_class`, `artifact_type`, and `contract_version` without inspecting payload contents.
- Sidecar manifests and data lake records should carry envelope fields alongside the payload contract to keep lineage, routing, and compatibility deterministic.
- Raw DOCX inputs may carry the envelope even when no payload contract is attached yet (`contract_name=null`, `contract_version=null`, `lifecycle_stage=raw`), keeping ingestion traceable without redefining schemas.
- Key payload contracts expected to travel inside the envelope: `meeting_minutes_record`, `reviewer_comment_set`, `comment_resolution_matrix`, `comment_resolution_matrix_spreadsheet_contract`, `working_paper_input`, `program_brief`, `study_readiness_assessment`, and `next_best_action_memo`.

## Versioning and compatibility
- Changes to contracts follow the semantic rules in `CONTRACT_VERSIONING.md` and the compatibility policy in `docs/contract-versioning.md` (required version fields plus compatible/minor/breaking change definitions).
- Breaking changes require architecture review approval before publishing a new major and must include migration guidance for operational engines.

## Contract inventory
- working_paper_input — structured intake for working paper revisions.
- reviewer_comment_set — normalized comment batches ready for resolution.
- comment_resolution_matrix — canonical mapping from comments to dispositions/actions.
- comment_resolution_matrix_spreadsheet_contract — official human-facing spreadsheet interface (exact headers/order, normalized mapping, input vs. adjudication guidance).
- pdf_anchored_docx_comment_injection_contract — authoritative PDF line-anchored insertion contract for turning resolution matrices + PDF anchors into commented DOCX outputs with mandatory audit reports and fixed canonical column order.
- meeting_agenda_contract — canonical agenda-generation interface that turns prior minutes + comment resolution matrices (plus optional submitted comments, prior agendas, and policy context) into the next agenda with traceable sections, carry-forward items, decisions, risks, pre-reads, and attendees.
- meeting_minutes — canonical transcript-to-minutes contract with required JSON + DOCX + validation report outputs; governed by `contracts/meeting_minutes_contract.yaml` and registered in `contracts/standards-manifest.json` (no extra fields allowed).
- standards_manifest — registry of published contract versions and status.
- provenance_record — reusable provenance record for contract artifacts and runs.
- program_brief — program-level decision readiness snapshot pulling from decision, risk, assumption, and milestone contracts.
- study_readiness_assessment — gate-based readiness assessment with missing artifact reporting and dependency-aware blockers.
- next_best_action_memo — prioritized action list with decision, risk, assumption, and milestone linkages.
- decision_log — structured decisions with readiness, evidence, options, and dependencies.
- risk_register — required risk categories (technical, data, schedule, stakeholder, process/legal, coordination, narrative) with decision-readiness effects.
- assumption_register — validated assumptions with evidence, dependencies, and mitigation plans.
- milestone_plan — dependency-aware milestone tracking with decision gates and readiness assessments.
- external_artifact_manifest — canonical manifest for artifacts stored on local or network storage outside GitHub, including storage_kind, local_path, checksum, and lineage links.

The comment resolution matrix spreadsheet contract is now part of the standards layer for user-visible artifacts. Downstream repos must preserve the exact headers and order defined in `contracts/schemas/comment_resolution_matrix_spreadsheet_contract.schema.json` when importing/exporting spreadsheets. Metadata fields (provenance ids, validation flags, run ids) must not be added to the visible sheet by default; place them in sidecars or hidden worksheets unless a formal contract update is published.

`spectrum-systems` is the czar repo for this contract. `working-paper-review-engine` must emit the canonical spreadsheet shape and `comment-resolution-engine` must ingest/export it without renaming or reordering columns; sibling repos must treat this contract as authoritative rather than redefining matrix layouts.

`pdf_anchored_docx_comment_injection_contract` is the czar-level law for injecting DOCX comments from resolution matrices using PDF page + line anchors. Engines must verify PDF anchors via target excerpts before mapping into DOCX text, enforce canonical column order and unique `comment_id`/`comment_id+revision_id` keys, fail loudly on ambiguity, preserve the source DOCX, and emit the mandated audit report fields for every attempted insertion.
