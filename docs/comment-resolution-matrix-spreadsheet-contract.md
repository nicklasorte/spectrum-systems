# Comment Resolution Matrix Spreadsheet Contract

This document canonizes the human-facing spreadsheet interface for the comment resolution matrix used across the czar repo org. It locks the exact headers, order, and semantics that downstream systems must honor when importing or exporting user-visible matrices.

## Canonical headers and order
The headers **must** appear exactly as written and in this exact order:
1. Comment Number
2. Reviewer Initials
3. Agency
4. Report Version
5. Section
6. Page
7. Line
8. Comment Type: Editorial/Grammar, Clarification, Technical
9. Agency Notes
10. Agency Suggested Text Change
11. NTIA Comments
12. Comment Disposition
13. Resolution

The example at `examples/comment-resolution-matrix-spreadsheet.csv` preserves this order and header text, including the comma within the Comment Type label.

## Column semantics
- **Comment Number → comment_number (input)**: Sequential identifier from the agency sheet; preserves row mapping.
- **Reviewer Initials → reviewer_initials (input)**: Reviewer attribution in compact form.
- **Agency → agency (input)**: Submitting agency.
- **Report Version → report_version (input)**: Revision anchor tying each row to the working paper under adjudication (e.g., rev1, rev2). Blank cells in single-revision runs map to rev1.
- **Section → section (input)**: Section number/title referenced by the comment.
- **Page → page (input)**: Page number referenced in the working paper.
- **Line → line (input)**: Line number or range within the page.
- **Comment Type: Editorial/Grammar, Clarification, Technical → comment_type (input)**: Classification; allowed values: Editorial/Grammar, Clarification, Technical.
- **Agency Notes → agency_notes (input)**: Context, rationale, or references from the agency.
- **Agency Suggested Text Change → agency_suggested_text_change (input)**: Verbatim text the agency proposes to add or replace.
- **NTIA Comments → ntia_comments (adjudication output)**: Reviewer/adjudicator rationale.
- **Comment Disposition → comment_disposition (adjudication output)**: Resolution decision (e.g., Accepted, Partially Accepted, Out of Scope).
- **Resolution → resolution (adjudication output)**: Final resolution text or action.

## Required vs. adjudication fields
- **Input columns required on ingest (must exist, may be blank only where noted)**: Comment Number; Reviewer Initials; Agency; Report Version; Section; Page; Line; Comment Type: Editorial/Grammar, Clarification, Technical; Agency Notes; Agency Suggested Text Change.
- **Adjudication output columns (may be blank on ingest, populated downstream)**: NTIA Comments; Comment Disposition; Resolution.
- MVP flow: `input matrix + working paper revision(s) -> adjudicated matrix` (outputs fill NTIA Comments, Comment Disposition, Resolution).

## Normalized keys
Normalized internal keys allow systems to work in snake_case while preserving the exact spreadsheet headers for I/O:
- Comment Number → `comment_number`
- Reviewer Initials → `reviewer_initials`
- Agency → `agency`
- Report Version → `report_version`
- Section → `section`
- Page → `page`
- Line → `line`
- Comment Type: Editorial/Grammar, Clarification, Technical → `comment_type`
- Agency Notes → `agency_notes`
- Agency Suggested Text Change → `agency_suggested_text_change`
- NTIA Comments → `ntia_comments`
- Comment Disposition → `comment_disposition`
- Resolution → `resolution`

Internal models may use normalized keys, but user-facing spreadsheets must keep the official headers and ordering.

## Compatibility guidance for downstream repos
- `comment-resolution-engine` must treat this spreadsheet as the primary import/export contract; no silent header renames.
- `spectrum-pipeline-engine` orchestration should accept and emit this exact shape instead of redefining a matrix layout.
- Future systems may enrich internal models but must preserve this interface for user-visible spreadsheets unless a new standard is formally adopted.
- Downstream repos must not introduce visible metadata columns to user artifacts; use sidecars or hidden worksheets when metadata is needed.

## Metadata handling policy
- Do **not** add default visible metadata columns (provenance ids, validation flags, run ids) to the canonical sheet.
- Place machine metadata in sidecar JSON/YAML files that travel with the spreadsheet, or in hidden worksheets when spreadsheet software requires embedded metadata.
- Only add new visible columns through a formal contract update.

## Validation guidance
- Fail fast if any required header is missing or renamed.
- Preserve the exact header order on export.
- Accept blank adjudication columns on input; populate them during adjudication.
- Ensure Comment Type values are one of {Editorial/Grammar, Clarification, Technical}.
- Map `Report Version` to the working paper revision; reject mismatches or ambiguous revisions.
- Normalize internal processing via the snake_case mapping, but preserve human headers on every user-facing artifact.

## Machine-readable artifacts
- Schema: `contracts/schemas/comment_resolution_matrix_spreadsheet_contract.schema.json`
- Contract instance: `contracts/examples/comment_resolution_matrix_spreadsheet_contract.json`
- Example spreadsheet: `examples/comment-resolution-matrix-spreadsheet.csv`
