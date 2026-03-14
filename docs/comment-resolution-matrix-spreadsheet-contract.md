# Comment Resolution Matrix Spreadsheet Contract

This document canonizes the human-facing spreadsheet interface for the comment resolution matrix used across the czar repo org. It locks the exact headers, order, and semantics that downstream systems must honor when importing or exporting user-visible matrices.

## Authority and scope
- `spectrum-systems` is the governing source for this matrix contract; no sibling or downstream repo may redefine the headers, order, or semantics.
- `contracts/schemas/comment_resolution_matrix_spreadsheet_contract.schema.json` is the machine-readable source of truth; this document is the human-readable companion.
- `working-paper-review-engine` (producer) must emit this exact shape; `comment-resolution-engine` (consumer) must ingest/export this exact shape; other repos (e.g., `spectrum-pipeline-engine`) must treat this contract as non-negotiable.
- Visible columns must match the canonical headers below—no freelancing, renaming, or reordering. Metadata belongs in sidecars or hidden sheets per the policy below.

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
- **Optional input columns**: none. Importers must reject visible columns beyond the canonical list.
- **Generated output columns (populated by adjudication systems)**: NTIA Comments; Comment Disposition; Resolution.
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

## Header normalization rules
- Preserve the exact human headers (casing, punctuation, and spacing) on every visible sheet.
- Trim leading/trailing whitespace on ingest, then map headers to snake_case via the normalized key map above (no aliases).
- Normalization is one-way: internal models may use snake_case, but exports must rehydrate the canonical headers in the fixed order.

## Completion semantics
- **Open rows**: `Comment Disposition` blank or `Pending`.
- **Completed rows**: `Comment Disposition` in {Accepted, Partially Accepted, Rejected, Out of Scope} **and** `Resolution` populated (non-blank).
- `NTIA Comments` is recommended for completed rows but not required to mark completion.
- Engines must not mark a row complete unless both disposition and resolution satisfy the rules above.

## Compatibility guidance for downstream repos
- `comment-resolution-engine` must treat this spreadsheet as the primary import/export contract; no silent header renames.
- `spectrum-pipeline-engine` orchestration should accept and emit this exact shape instead of redefining a matrix layout.
- Future systems may enrich internal models but must preserve this interface for user-visible spreadsheets unless a new standard is formally adopted.
- Downstream repos must not introduce visible metadata columns to user artifacts; use sidecars or hidden worksheets when metadata is needed.

## Metadata handling policy
- Do **not** add default visible metadata columns (provenance ids, validation flags, run ids) to the canonical sheet.
- Place machine metadata in sidecar JSON/YAML files that travel with the spreadsheet, or in hidden worksheets when spreadsheet software requires embedded metadata.
- Only add new visible columns through a formal contract update.

## Output workbook expectations
- Preferred formats: CSV or XLSX.
- Primary sheet name: `Comment Resolution Matrix`.
- Primary sheet headers: exactly the canonical header list above, in order; no additional visible columns.
- Hidden worksheets may carry metadata; visible sheets must only expose the canonical columns.

## Example layout
```
Comment Number,Reviewer Initials,Agency,Report Version,Section,Page,Line,Comment Type: Editorial/Grammar, Clarification, Technical,Agency Notes,Agency Suggested Text Change,NTIA Comments,Comment Disposition,Resolution
1,AB,NOAA,rev1,2.3,14,120-130,Technical,"Request propagation model parameters and datasets used.","Add explanation of the clutter loss model and cite the data source.",,Pending,
2,CD,FAA,rev1,3.1,22,45,Clarification,"Clarify how the guard band for Scenario A was selected.","Add a sentence describing the guard band rationale and pointer to supporting study.","NTIA agrees additional context needed.",Accepted,"Guard band rationale inserted in Section 3.1 with citation to guard band study."
```

## Validation guidance
- Fail fast if any required header is missing or renamed.
- Preserve the exact header order on export.
- Reject matrices that introduce extra visible columns; exports must emit only the canonical headers.
- Accept blank adjudication columns on input; populate them during adjudication.
- Ensure Comment Type values are one of {Editorial/Grammar, Clarification, Technical}.
- Map `Report Version` to the working paper revision; reject mismatches or ambiguous revisions.
- Normalize internal processing via the snake_case mapping, but preserve human headers on every user-facing artifact.

## Machine-readable artifacts
- Schema: `contracts/schemas/comment_resolution_matrix_spreadsheet_contract.schema.json`
- Contract instance: `contracts/examples/comment_resolution_matrix_spreadsheet_contract.json`
- Example spreadsheet: `examples/comment-resolution-matrix-spreadsheet.csv`
