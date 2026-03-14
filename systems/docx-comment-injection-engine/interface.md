# DOCX Comment Injection Engine — Interface (SYS-008)

## Purpose
Render anchored comments and dispositions into DOCX deliverables without violating the canonical contracts governing comment matrices and anchored payloads.

## Inputs
- `comment_resolution_matrix_spreadsheet_contract` (authoritative headers/order).
- Anchored payloads conforming to `pdf_anchored_docx_comment_injection_contract`.
- Source DOCX (and reference PDF) representing the target working paper revision.
- Provenance records covering sources, reviewers, dispositions, and anchor mapping.
- Run configuration: contract versions, prompt/rule versions, model hash, deterministic seed.

## Contracts and Schemas
- Must consume `comment_resolution_matrix_spreadsheet_contract` and `pdf_anchored_docx_comment_injection_contract` exactly as published in `contracts/standards-manifest.json`.
- Provenance must align to `docs/data-provenance-standard.md`; run manifest must capture contract versions and anchors applied.

## Outputs
- Annotated DOCX with injected comments/dispositions anchored to PDF/DOCX locations.
- Updated `comment_resolution_matrix_spreadsheet_contract` with injection status and anchor confirmation.
- Run manifest including applied anchors, any manual overrides, and validation results.

## Validation Rules
- Block on header/order deviations in the spreadsheet contract.
- Reject anchors that cannot be matched to the supplied PDF/DOCX revision.
- Require byte-level parity checks where feasible to confirm deterministic injection.
- Do not emit outputs if provenance is incomplete or conflicting.

## Human Review Points
- Validate anchor fidelity for a sample of high-priority comments.
- Confirm no fields were added/removed from the spreadsheet contract during injection.
- Approve run manifest before publishing annotated DOCX downstream.
