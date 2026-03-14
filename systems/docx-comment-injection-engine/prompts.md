# DOCX Comment Injection Engine — Prompts and Rules (SYS-008)

## Prompt Guidance
- Maintain contract field names and ordering; no free-form additions to the spreadsheet contract.
- Require explicit anchor references (page/paragraph/section) and disposition text for every injected comment.
- Use deterministic settings (temperature zero, stable sorting) to ensure reproducible DOCX outputs or hashes.

## Rules
- Validate anchors against the supplied PDF/DOCX revision before insertion; ambiguous anchors must be flagged for human review.
- Do not alter upstream IDs; propagate provenance into the manifest and updated matrix.
- Block emission if contract versions do not match manifest pins or if provenance is incomplete.

## Manifest Requirements
- Record prompt/rule versions, model hash, contract versions, template identifiers, and deterministic seed.
- Capture any manual anchor overrides with reviewer identity and timestamp.
