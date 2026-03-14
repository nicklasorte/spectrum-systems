# DOCX Comment Injection Engine — Design (SYS-008)

## Purpose
Provide deterministic, contract-aligned insertion of comments and dispositions into DOCX deliverables with preserved anchors and provenance.

## Bottleneck Addressed
BN-001: Manual DOCX insertion of comments/dispositions causes delays and contract drift, undermining traceability to working paper revisions.

## Inputs
- `comment_resolution_matrix_spreadsheet_contract` with canonical headers/order.
- Anchored payloads following `pdf_anchored_docx_comment_injection_contract`.
- Source DOCX and PDF for the target revision.
- Provenance records and prior manifests for lineage.
- Configuration: contract versions, prompt/rule versions, model hash, deterministic seed, template version.

## Processing Pipeline
1. **Validation**: Confirm spreadsheet headers/order and anchored payload schema versions match manifest pins.
2. **Anchor Resolution**: Map anchors to DOCX locations; verify PDF/DOCX revision alignment.
3. **Injection**: Apply comments/dispositions into DOCX deterministically; preserve identifiers and ordering.
4. **Parity Checks**: Compare injected DOCX against expected anchor positions; detect collisions/overwrites.
5. **Manifest Publication**: Emit run manifest with inputs, applied anchors, validation outcomes, and replay parameters.

## Failure Boundaries
- Anchor mismatch to supplied revision → block with `ANCHOR_MISMATCH`.
- Spreadsheet contract drift → block with `CONTRACT_HEADER_DRIFT`.
- Missing provenance → block with explicit provenance error; no outputs emitted.

## Outputs
- Annotated DOCX aligned to anchored payloads.
- Updated `comment_resolution_matrix_spreadsheet_contract` reflecting injection status.
- Run manifest capturing inputs, versions, anchors applied, and validation results.

## Evaluation Plan
- Schema validation for both input contracts and updated matrix.
- Anchor fidelity tests (known anchor fixtures; intentional mismatches).
- Determinism replay on the same inputs to ensure byte-stable DOCX where feasible or stable hashes when DOCX hashing is used.
- Failure-case injection for missing provenance and header drift.

## Open Risks
- DOCX rendering differences across environments may affect byte-level determinism; hash-based parity may be required.
- Anchor resolution may depend on PDF-to-DOCX fidelity; templates must be versioned and pinned.
