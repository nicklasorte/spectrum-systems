# Comment Resolution Engine — System Design

## Purpose
Systematically ingest, structure, and resolve agency comments with traceable dispositions that align to report sections and decision records.

## Problem Statement
Comment cycles stall reports because feedback arrives in heterogeneous formats, duplicates accumulate, and disposition text is crafted manually without consistent traceability to sources or sections.

## Inputs
- Comment spreadsheets and narrative submissions
- Report sections with anchors for mapping
- Workflow rules (priority, required response types, routing)
- Prior dispositions and related issues for context

## Schemas Used
- `comment-schema` for normalized comment records and statuses
- `issue-schema` for mapping comments to related questions or blockers
- Section mapping schema (anchors to report structure) for provenance

## Processing Pipeline
1. Ingest and normalize comments to `comment-schema` with source locations.
2. Cluster and de-duplicate by topic, section, and authority.
3. Map each comment to report sections and related issues.
4. Generate draft dispositions and response text using prompt-standard templates.
5. Apply validation against schemas and workflow rules.
6. Route to human review for high-impact or low-confidence items.
7. Publish structured responses and update status for each comment.

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
- Dedupe and clustering validation for contested topics
- Approval of draft disposition language before publication
- Escalation for policy-sensitive or cross-agency conflicts

## Evaluation Criteria
- Mapping accuracy between comments, sections, and issues
- Completeness of traceability fields and status updates
- Clarity and compliance of draft dispositions with workflow rules
- Deterministic outputs under repeated runs

## Failure Modes
- Incorrect section or issue mapping leading to misrouted dispositions
- Over- or under-clustering that hides unique concerns
- Draft text that contradicts policy constraints or schema requirements
- Missing provenance links that block auditability

## Future Implementation Repository
`spectrum-systems-comment-resolution-engine`
