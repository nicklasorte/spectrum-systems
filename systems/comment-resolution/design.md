# Comment Resolution Engine — Design (SYS-001)

## Purpose
Ingest, normalize, and resolve agency comments with explicit revision lineage and deterministic dispositions suitable for report integration.

## Problem Statement
Comment cycles stall because comments arrive in mixed formats, revisions drift, and disposition text is crafted manually without consistent traceability.

## Inputs
- Comment spreadsheets or narratives (when multiple PDFs are supplied the `Revision` column is required).
- Working paper PDFs (rev1+ mapped deterministically in upload order).
- Section anchors and routing rules.
- Prior dispositions and related issues for context.

## Schemas
- `schemas/comment-schema.json` — authoritative comment record and disposition status.
- `schemas/issue-schema.json` — linked issues/backlog items.
- `schemas/provenance-schema.json` — lineage for every record and run manifest references.

## Processing Pipeline
1. Ingest and normalize comments to `comment-schema.json`; attach declared revision and source anchors.
2. Cluster/dedupe by topic, section, and authority with thresholds aligned to the rule pack.
3. Map to sections and related issues; fail fast if any referenced revision is missing.
4. Draft dispositions using `prompts/comment-resolution.md` and `rules/comment-resolution/`.
5. Validate schema conformance, revision lineage, and confidence thresholds; emit structured validation errors.
6. Route low-confidence or policy-sensitive items to human review before publication.
7. Publish structured records plus a run manifest (model, prompt, rule, schema versions).

## Example Input
```json
{
  "comment_id": "AGY-12",
  "source_document": "AgencyA_Comments.pdf",
  "source_location": "p.4, para 2",
  "section_reference": "3.2 Interference Analysis",
  "text": "Provide justification for the assumed clutter category in Urban Core cases.",
  "priority": "high",
  "agency": "Agency A"
}
```

## Example Output
```json
{
  "comment_id": "AGY-12",
  "section_reference": "3.2 Interference Analysis",
  "related_issue_ids": ["ISS-104"],
  "draft_disposition": "Include citation to ITU-R P.2108 for clutter classification and add sensitivity results for Urban Core assumptions.",
  "status": "proposed",
  "provenance": {
    "source_document": "AgencyA_Comments.pdf",
    "source_location": "p.4, para 2"
  },
  "owner": "Comment Resolution Engine",
  "review_required": true
}
```

## Human Review Points
- Validate clustering decisions for contested topics.
- Approve disposition language and tone before release.
- Escalate policy-sensitive or cross-agency conflicts.

## Evaluation Criteria
- Mapping accuracy between comments, sections, and issues.
- Completeness of traceability fields and revision lineage.
- Deterministic outputs under repeated runs with the same manifest.
- Compliance with blocking rules in `systems/comment-resolution/interface.md`.

## Failure Modes
- Incorrect section or issue mapping leading to misrouted dispositions.
- Over- or under-clustering that hides unique concerns.
- Draft text that contradicts policy constraints or schema requirements.
- Missing provenance links or run manifest references.

## Implementation Notes
Implementation lives in a separate repository. This design, schemas, prompts, and evaluation plan must be satisfied before code changes.
