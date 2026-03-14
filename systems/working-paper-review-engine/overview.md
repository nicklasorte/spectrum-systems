# Working Paper Review Engine (SYS-007)

Purpose: ingest working paper drafts, normalize reviewer feedback, and emit canonical comment artifacts for downstream resolution and orchestration.

- **Bottleneck**: BN-001 — manual comment intake and normalization delay disposition drafting and traceability.
- **Inputs**: `working_paper_input` (PDF/DOCX + metadata), review guidance, reviewer identity and role metadata, prior comment sets for linkage, templates for anchored comments.
- **Outputs**: `reviewer_comment_set`, `comment_resolution_matrix_spreadsheet_contract`, anchored comment packages for DOCX insertion, run manifest with provenance and contract versions.
- **Upstream Dependencies**: working paper authorship, review assignments, contract versions from `contracts/standards-manifest.json`.
- **Downstream Consumers**: comment-resolution-engine, docx-comment-injection-engine, spectrum-pipeline-engine, meeting-agenda generation.
- **Related Assets**: `docs/comment-resolution-matrix-spreadsheet-contract.md`, `CONTRACTS.md`, `workflows/working-paper-review-engine.md`.
- **Lifecycle Status**: Design drafted; czar coverage added; implementation repo must declare pins to this spec before build.

Outputs must preserve reviewer identity, source locations, and revision lineage; spreadsheet headers/order must follow the canonical contract.
