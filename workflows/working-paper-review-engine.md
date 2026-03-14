# Working Paper Review Engine

## Purpose
Normalize reviewer feedback on working papers into governed comment artifacts.

## Steps
1. Validate working paper revision metadata and reviewer assignments.
2. Anchor comments to pages/sections; flag ambiguous anchors for human review.
3. Normalize feedback into `reviewer_comment_set`.
4. Render `comment_resolution_matrix_spreadsheet_contract` with canonical headers/order and provenance.
5. Emit anchored DOCX payloads (optional) and run manifest with contract/prompt/rule versions.

## References
- Interface: `systems/working-paper-review-engine/interface.md`
- Design: `systems/working-paper-review-engine/design.md`
- Contracts: `contracts/standards-manifest.json`, `docs/comment-resolution-matrix-spreadsheet-contract.md`
- Prompts: `systems/working-paper-review-engine/prompts.md`
- Evaluation: `systems/working-paper-review-engine/evaluation.md`
