# Artifact Contract Guide

This guide explains the canonical contracts published in `contracts/schemas/` and how downstream repos should use them. Each artifact includes provenance fields to satisfy `docs/data-provenance-standard.md`.

## Common metadata
All contracts carry:
- `artifact_type`, `artifact_id`, `artifact_version`, `schema_version`, `standards_version`
- `record_id` for diffing, `run_id` for execution lineage, `working_paper_revision` where applicable
- `created_at`, `created_by`, `source_repo`, `source_repo_version`
- `input_artifacts` to enumerate parent artifacts with type and version

### working_paper_input
- Purpose: canonical intake of a working paper revision with structure for downstream review engines.
- Required: `artifact_id`, `artifact_type`, `artifact_version`, `schema_version`, `standards_version`, `record_id`, `working_paper_revision`, `run_id`, `created_at`, `created_by`, `source_repo`, `source_repo_version`, `title`, `summary`, `sections`, `submission_window`, `status`.
- Optional: `primary_author`, `contributors`, `topics`, `document_checksums`, `input_artifacts`.
- Downstream usage: bootstraps reviewer workloads, normalizes references for `reviewer_comment_set`, and anchors later dispositions to a specific revision.

### reviewer_comment_set
- Purpose: normalized batch of reviewer comments tied to a working paper revision.
- Required: metadata fields above plus `comment_set_id`, `working_paper_id`, `working_paper_revision`, `comments`.
- Comment required fields: `comment_id`, `text`, `severity`, `priority`, `location`, `status`, `proposed_disposition`, `provenance_id`.
- Optional: `tags`, `linked_issue_ids`, `attachments`, `input_artifacts`.
- Downstream usage: feeds comment-resolution-engine; enables deterministic mapping from comments to resolutions and audit trails back to source documents.

### comment_resolution_matrix
- Purpose: authoritative mapping from comments to dispositions, actions, and validation status.
- Required: metadata fields plus `matrix_id`, `comment_set_id`, `entries`.
- Entry required fields: `comment_id`, `resolution_status`, `response_text`, `action_items`, `validated_by`, `applies_to_revision`.
- Optional: `evidence_links`, `validation_notes`, `input_artifacts`.
- Downstream usage: exported to working-paper-review-engine and reporting pipelines; used to verify closure of every comment against a fixed revision.

### comment_resolution_matrix_spreadsheet_contract
- Purpose: canonical human-facing spreadsheet interface for the comment resolution matrix with fixed headers and ordering.
- Required: metadata fields plus `ordered_headers`, `headers` (definitions with normalized keys and roles), `normalized_key_map`, `input_columns`, `adjudication_columns`, `comment_type_values`, `metadata_handling`, `compatibility`, `validation_rules`.
- Header order: `Comment Number`, `Reviewer Initials`, `Agency`, `Report Version`, `Section`, `Page`, `Line`, `Comment Type: Editorial/Grammar, Clarification, Technical`, `Agency Notes`, `Agency Suggested Text Change`, `NTIA Comments`, `Comment Disposition`, `Resolution`.
- Downstream usage: comment-resolution-engine and spectrum-pipeline-engine import/export spreadsheets using these exact headers; normalized keys may be used internally but exports must preserve official headers. No additional visible metadata columns; place metadata in sidecars or hidden worksheets.

### standards_manifest
- Purpose: machine-readable registry of contract versions and stability state.
- Required: `artifact_type`, `artifact_id`, `artifact_version`, `schema_version`, `standards_version`, `created_at`, `created_by`, `source_repo`, `source_repo_version`, `contracts`.
- Contract entries: `artifact_type`, `schema_version`, `status`, `intended_consumers`.
- Downstream usage: system-factory mirrors this manifest when scaffolding repos; engines pin against listed versions.

### provenance_record
- Purpose: reusable provenance entity for contract artifacts and run chains.
- Required: metadata fields plus `record_type`, `entity_id`, `activity`, `agents`, `derived_from`, `lineage`.
- Optional: `review_status`, `reviewed_by`, `review_notes`, `quality_status`.
- Downstream usage: stored alongside every contract instance to prove lineage, run parameters, and review outcomes.
