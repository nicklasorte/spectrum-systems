# Working Paper Review Engine — Interface (SYS-007)

## Purpose
Normalize working paper reviews into contract-governed comment sets and matrices consumable by downstream resolution and orchestration engines.

## Inputs
- `working_paper_input` (PDF/DOCX) with revision identifiers and metadata.
- Reviewer assignments and guidance (roles, scopes, deadlines).
- Prior `reviewer_comment_set` and `comment_resolution_matrix_spreadsheet_contract` entries for linkage and carry-over.
- Optional policy/context notes to aid categorization.

## Contracts and Schemas
- Must emit `reviewer_comment_set` and `comment_resolution_matrix_spreadsheet_contract` exactly as defined in `contracts/standards-manifest.json`.
- Provenance metadata must align to `docs/data-provenance-standard.md`, capturing reviewer, document revision, page/section anchors, and run manifest versions.
- PDF/DOCX anchoring must follow `contracts/pdf_anchored_docx_comment_injection_contract.json` when producing anchored DOCX outputs.

## Outputs
- Normalized `reviewer_comment_set` with unique IDs, anchors, categories, and provenance.
- `comment_resolution_matrix_spreadsheet_contract` with fixed headers/order for downstream ingestion.
- Anchored DOCX comment payloads (optional) for docx-comment-injection-engine.
- Run manifest listing contract versions, prompts/rules, model hash, and deterministic replay parameters.

## Validation Rules
- Reject inputs without revision identifiers or missing reviewer identity.
- Enforce canonical spreadsheet headers/order; fail on deviations.
- Require anchor fidelity: every comment must map to a document location; ambiguous anchors must be flagged for human review.
- Deterministic mode required for repeat runs with unchanged inputs.

## Human Review Points
- Spot-check anchor accuracy and category assignments.
- Validate normalization of reviewer intent into the canonical contract.
- Approve run manifest before forwarding matrices to downstream engines.
