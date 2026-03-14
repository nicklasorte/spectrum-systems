# Working Paper Review Engine — Evaluation (SYS-007)

## Goals
Confirm normalized comment artifacts are contract-compliant, anchor-accurate, and deterministic.

## Test Dimensions
- **Contract Conformance**: Validate `reviewer_comment_set` and `comment_resolution_matrix_spreadsheet_contract` against canonical schemas, including header/order checks for the spreadsheet.
- **Anchoring Accuracy**: Provide fixtures with known page/section anchors; assert correct mapping and error handling for ambiguous anchors.
- **Deduplication & Carry-Forward**: Ensure duplicates across revisions are merged with preserved provenance; carry-forward items retain lineage.
- **Determinism**: Replay runs with identical inputs/prompts/rules/model hash to confirm byte-stable outputs aside from run metadata.
- **Failure Modes**: Inject missing revision metadata, absent reviewer identity, and malformed spreadsheet headers to confirm blocking behavior.

## Fixtures (to be added)
- Clean working paper with aligned anchors and reviewer notes.
- Ambiguous anchor sample to test human-review gating.
- Duplicate comment set across revisions to test lineage preservation.

## Human Review Hooks
- Validate ambiguous anchor handling and category assignments.
- Approve manifest before forwarding artifacts downstream.
