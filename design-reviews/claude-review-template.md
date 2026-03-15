# YYYY-MM-DD - <scope> Claude Design Review

Deterministic finding IDs are review-scoped:
- Start at `[F-1]` for the first required change, recommended enhancement, or follow-up that appears in this markdown and increment as new findings surface. Numbering resets per review slug and must not be renumbered after publication.
- Reuse those exact IDs as `findings[*].id` in the paired JSON actions file. Keep gaps `[G1]`, risks `[R1]`, recommendations `[REC-1]`, and actions `[A-1]` stable and cross-referenced to the relevant `[F-#]`.
- Minimal mapping example: Markdown `[F-1] Deterministic IDs keep markdown and JSON aligned` ↔ JSON `"findings": [{"id": "F-1", "title": "Deterministic IDs keep markdown and JSON aligned", ...}]`

Tag every required change, recommendation, follow-up trigger, and action below with its stable marker so automation can match sections directly to JSON entries. Use the same slug across both filenames and inside `review_metadata` to preserve traceability.

> Claude: Produce two artifacts for every review.
> 1) This markdown file using the sections below.
> 2) A JSON actions file at `design-reviews/YYYY-MM-DD-<slug>.actions.json` that validates against `design-reviews/claude-review.schema.json` with root fields: `schema_version`, `review_metadata`, `findings`, `summary`, `recommendations`, `actions`, `follow_up`. The JSON `findings[*].id` values must match the `[F-#]` markers in this markdown.

JSON findings entries must include: `id` (`F-1`), `severity` (critical|high|medium|low), `category`, `title`, `description`, `recommended_action` (string or list of strings), `files_affected` (list or string), `create_issue` (boolean), `suggested_issue_title`, `suggested_labels`, and optional `target_repo`/`trigger`. When follow-up is required, add scheduling metadata: `follow_up_trigger` (e.g., after merge of related PR, before next release, after compliance scan, next architecture review) and `due_date` (YYYY-MM-DD). Keep IDs consistent across markdown and JSON.

## 1. Review Metadata
- Review ID: YYYY-MM-DD-<slug>
- Repository:
- Scope:
- Review artifacts: `design-reviews/YYYY-MM-DD-<slug>.md` + `design-reviews/YYYY-MM-DD-<slug>.actions.json`
- Reviewer/agent: Claude (Reasoning Agent)
- Commit/version reviewed:
- Inputs consulted:

## 2. Scope
- In-bounds:
- Out-of-bounds:
- Rationale:

## 3. Executive Summary
- Key finding 1
- Key finding 2
- Key finding 3

## 4. Strengths
- Validated positive 1
- Validated positive 2

## 5. Structural Gaps (Required Changes)
- [F-1][G1] Gap / required change — evidence/reference
- [F-2][G2] Gap / required change — evidence/reference

## 6. Risk Areas (Finding-linked)
- [F-3][R1] Risk statement — severity/likelihood — rationale — linked gaps
- [F-4][R2] Risk statement — severity/likelihood — rationale — linked gaps

## 7. Recommendations
- [REC-1] Recommendation / enhancement — mapped to gaps/risks with expected outcome — source findings [F-#]
- [REC-2] Recommendation / enhancement — mapped to gaps/risks with expected outcome — source findings [F-#]

## 8. Priority Classification
- [REC-1] Priority: Critical | High | Medium | Low — rationale
- [REC-2] Priority: Critical | High | Medium | Low — rationale

## 9. Extracted Action Items
1. [A-1] Owner: TBD — Item — expected artifact — acceptance criteria — source [REC-#] — supports findings [F-#]
2. [A-2] Owner: TBD — Item — expected artifact — acceptance criteria — source [REC-#] — supports findings [F-#]

## 10. Blocking Items
- [F-#] Blocking item — condition to clear

## 11. Deferred Items
- [F-#] Deferred item — review trigger/condition
