# Working Paper Review Engine — Design (SYS-007)

## Purpose
Provide deterministic intake of working paper drafts, normalize reviewer feedback, and emit governed comment artifacts for downstream resolution and agenda orchestration.

## Bottleneck Addressed
BN-001: Manual intake and normalization of reviewer comments slows disposition drafting and erodes traceability to working paper revisions.

## Inputs
- `working_paper_input` (PDF/DOCX) with revision identifiers and metadata.
- Reviewer assignments, scopes, and guidance.
- Prior comment sets and matrices for carry-forward and duplicate detection.
- Anchoring context: section anchors, template identifiers, and PDF location references.

## Processing Pipeline
1. **Intake & Validation**: Verify revision metadata, reviewer identity, and working paper completeness.
2. **Anchoring**: Map comments to precise locations (page/paragraph/section anchors); flag ambiguous anchors for human review.
3. **Normalization**: Convert raw feedback into `reviewer_comment_set` with categories, priorities, and provenance.
4. **Matrix Construction**: Render `comment_resolution_matrix_spreadsheet_contract` with fixed headers/order; include linkage to anchors and prior cycles.
5. **Quality & Drift Checks**: Deduplicate comments, detect missing anchors, and validate contract conformance.
6. **Manifest & Publication**: Emit run manifest capturing contract versions, prompt/rule versions, model hash, and determinism parameters.

## Failure Boundaries
- Missing revision identifiers or reviewer identity → block and surface `INPUT_METADATA_MISSING`.
- Anchor ambiguity beyond tolerance → require human review before publication.
- Spreadsheet header/order deviations → block with explicit schema error.

## Outputs
- `reviewer_comment_set`
- `comment_resolution_matrix_spreadsheet_contract`
- Anchored DOCX comment payloads (for docx-comment-injection-engine)
- Run manifest with provenance and replay parameters

## Evaluation Plan
- Contract validation for reviewer_comment_set and spreadsheet outputs.
- Anchor accuracy spot checks and failure-case injection.
- Determinism replay to confirm stable matrices given unchanged inputs.
- Duplicate detection scenarios to ensure idempotent outputs.

## Open Risks
- Source DOCX/PDF variability may complicate reliable anchoring.
- Reviewer free-form inputs may resist normalization without clear guidance; prompts/rules must be explicit.
- Downstream drift risk if spreadsheet contract changes without synchronized updates.
