# Prompts — Comment Resolution Engine

Primary prompt: `prompts/comment-resolution.md`.

- **Purpose**: Draft structured dispositions for each comment with section alignment and revision lineage.
- **Inputs**: Comment records (normalized to `schemas/comment-schema.json`), working paper context, section anchors, applicable revision mapping.
- **Outputs**: Disposition text, status, section references, and provenance fields aligned to `comment-schema` and `issue-schema`.
- **Constraints**: Deterministic style, explicit references to revisions, cite assumptions and sources, reject missing revision mappings.
- **Grounding Rules**: Prefer rule packs in `rules/comment-resolution/`; flag missing anchors; never invent sources.
- **Versioning**: Version string maintained in the prompt header; changes must trigger evaluation in `eval/comment-resolution`.
