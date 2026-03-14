# Working Paper Review Engine — Prompts and Rules (SYS-007)

## Prompt Guidance
- Extract comments with explicit anchors (page/paragraph/section) and reviewer identity; reject or flag when anchors are ambiguous.
- Normalize categories, priorities, and dispositions into the canonical fields; avoid free-form additions.
- Use temperature-zero prompts to preserve determinism; enforce consistent ordering (by section then comment_id).

## Rules
- Spreadsheet headers and order must match `comment_resolution_matrix_spreadsheet_contract`; never rename or reorder columns.
- Each comment must carry provenance (revision, reviewer, source location); missing fields block publication.
- Anchored DOCX payloads must align to `pdf_anchored_docx_comment_injection_contract` when produced.

## Manifest Requirements
- Record prompt/rule versions, model hash, contract versions, and deterministic seed.
- Capture any human-reviewed anchors or overrides with reviewer identity and timestamp.
