# Comment Resolution Engine (SYS-001)

Purpose: resolve agency comments deterministically with traceable dispositions tied to working paper revisions.

- **Bottleneck**: BN-001 — manual reconciliation of comments across revisions delays report publication.
- **Inputs**: Comment spreadsheets/narratives with required `Revision` column when multiple PDFs are supplied; working paper PDFs (rev1+); section anchors.
- **Outputs**: Structured comment records with dispositions, section mappings, revision lineage, provenance, and run manifest references.
- **Upstream Dependencies**: Source documents, section anchors, rule packs in `rules/comment-resolution/`.
- **Downstream Consumers**: Report drafting workflows, issue backlogs, decision artifacts.
- **Related Assets**: `schemas/comment-schema.json`, `schemas/issue-schema.json`, `prompts/comment-resolution.md`, `eval/comment-resolution`.
- **Lifecycle Status**: Design complete; evaluation scaffolding in place (`docs/system-status-registry.md`).
