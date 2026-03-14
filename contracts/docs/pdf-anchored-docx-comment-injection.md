# PDF-Anchored DOCX Comment Injection Contract

Authoritative contract for inserting Word comments based on PDF page + line anchors validated by excerpts. The PDF anchor is the source of truth; engines must never guess or rely on DOCX layout alone.

## Required inputs
- Resolution matrix aligned to the target revision.
- Source PDF generated from the same DOCX revision (line-number view).
- Source DOCX for comment insertion (preserved; do not overwrite).
- Optional insertion policy config for status normalization or eligibility tuning.

## Canonical row fields
- `comment_id`, `source_agency`, `comment_text`, `comment_response`, `status`, `revision_id`
- `pdf_page` (required, integer > 0), `pdf_line_number` (required, integer > 0)
- `target_excerpt` (required), `target_section_heading` (optional but recommended)
- `injection_text` (required and non-empty for eligible rows), `injection_mode`
- `anchor_confidence`, `notes`

## MVP anchor rules
- PDF page + line number is the primary placement constraint.
- Engines must verify `target_excerpt` in the PDF context before any DOCX insertion.
- Engines then map the verified excerpt into DOCX text; ambiguity is a failure.
- Fail loudly if the PDF anchor is missing or ambiguous, or if DOCX mapping is ambiguous.
- Never silently guess; optimize for wrong-placement prevention.

## Canonical insertion behavior
- Inject Word comments only for statuses eligible under the status policy.
- Skip rows marked complete, no action, not applicable, rejected, or blocked.
- `injection_text` must be non-empty for eligible rows.
- Preserve the original DOCX; emit a new commented DOCX output.

## Status policy
- Eligible: `pending_injection`, `requires_insertion`, `needs_injection_review`.
- Skip: `complete`, `no_action`, `not_applicable`, `rejected`, `blocked`.
- Normalization: map spreadsheet variants (e.g., “Pending”, “Needs insertion”, “N/A”, “Done”) into the canonical statuses before eligibility checks.

## Audit requirements
Every engine run must emit an injection report row with: `comment_id`, `pdf_page`, `pdf_line_number`, `target_excerpt`, `result` (inserted/skipped/failed), `reason`, `matched_pdf_text`, `matched_docx_text`, `matched_location`, `confidence`.

## Validation rules
- Required columns present and `comment_id` unique (or unique with `revision_id`).
- `pdf_page` and `pdf_line_number` are positive integers.
- `target_excerpt` is non-empty.
- `injection_text` is non-empty for insertion-eligible rows.
- Source PDF and DOCX correspond to the same `revision_id`.

## Implementation guidance
- Treat the PDF as the stable anchor view; use page + line to narrow search, then verify `target_excerpt`.
- Use `target_section_heading` as a narrowing hint when provided.
- Refuse insertion when anchors or mappings are ambiguous; all failures must be explicit and auditable.
- Output: commented DOCX plus audit report; keep the source DOCX intact.

## Fixtures
- Schema: `contracts/schemas/pdf_anchored_docx_comment_injection_contract.schema.json`
- JSON example: `contracts/examples/pdf_anchored_docx_comment_injection_contract.json`
- CSV rows (canonical headers): `contracts/examples/pdf_anchored_docx_comment_injection_entries.csv`
