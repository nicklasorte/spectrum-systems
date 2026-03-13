# Comment Resolution Prompt (v1.0)

## Purpose
Draft deterministic dispositions for agency comments with explicit section mapping and revision lineage.

## Inputs
- Comment records normalized to `schemas/comment-schema.json` (including `revision` when multiple PDFs are provided).
- Working paper context and section anchors for each revision.
- Applicable disposition/routing rules and style constraints.

## Outputs
- Updated comment records with disposition text, status, section mapping, `resolved_against_revision`, provenance, and run manifest reference.

## Constraints
- Follow `schemas/comment-schema.json` and `schemas/issue-schema.json` for linked issues.
- Never invent sections, sources, or revisions; flag when anchors or revisions are missing.
- Cite assumptions explicitly; maintain deterministic tone and formatting.
- Use rule packs in `rules/comment-resolution/` when provided.

## Grounding Rules
- Always reference the source document, page/paragraph, and revision.
- Maintain one-to-one mapping between comments and dispositions unless clustering is explicitly provided.
- If confidence is low or policy-sensitive language is detected, mark `review_required` and explain why.

## Verification
- Validate JSON structure matches the schemas.
- Confirm each comment has a mapped section, revision lineage, and provenance.
- Ensure run manifest ID is echoed so outputs are reproducible per `docs/reproducibility-standard.md`.
