# DOCX Comment Injection Engine — Evaluation (SYS-008)

## Goals
Ensure injected DOCX outputs preserve anchors, contracts, and determinism.

## Test Dimensions
- **Contract Conformance**: Validate incoming/outgoing `comment_resolution_matrix_spreadsheet_contract` and `pdf_anchored_docx_comment_injection_contract`.
- **Anchor Fidelity**: Use fixtures with known anchors; confirm correct placement and rejection of mismatched anchors.
- **Determinism**: Replay injections with identical inputs/configuration to confirm stable DOCX hashes or byte equivalence where feasible.
- **Failure Handling**: Inject header drift, missing provenance, and anchor mismatches to confirm blocking with explicit error codes.

## Fixtures (to be added)
- Clean anchored payload with deterministic anchors.
- Mismatched revision to trigger anchor failure.
- Spreadsheet with altered header/order to ensure blocking behavior.

## Human Review Hooks
- Spot-check anchor placements for high-priority comments.
- Verify manifest accuracy before distributing annotated DOCX.
