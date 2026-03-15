# YYYY-MM-DD - <scope> Claude Design Review

Use stable identifiers across both artifacts: findings `[F-1]`, gaps `[G1]`, risks `[R1]`, recommendations `[REC-1]`, and actions `[A-1]`. Finding IDs are the anchor for traceability—every `[F-#]` called out in this markdown **must** appear as the same `id` inside the JSON `findings` array. Number once per review in the order introduced and do not renumber after publication. Example: `[F-1] Deterministic IDs keep markdown and JSON aligned` in this file must map to `"id": "F-1"` inside `findings[0]` of `YYYY-MM-DD-<slug>.actions.json`. Tag every required change, recommendation, and action below with its stable marker so automation can match sections directly to JSON entries.

> Claude: Produce two artifacts for every review.
> 1) This markdown file using the sections below.
> 2) A JSON actions file at `design-reviews/YYYY-MM-DD-<slug>.actions.json` that validates against `design-reviews/claude-review.schema.json` with root fields: `schema_version`, `review_metadata`, `findings`, `summary`, `recommendations`, `actions`, `follow_up`. The JSON `findings[*].id` values must match the `[F-#]` markers in this markdown.

JSON findings entries must include: `id` (`F-1`), `severity` (critical|high|medium|low), `category`, `title`, `description`, `recommended_action` (string or list of strings), `files_affected` (list or string), `create_issue` (boolean), `suggested_issue_title`, `suggested_labels`, and optional `target_repo`/`follow_up_trigger`/`due_date` (YYYY-MM-DD). Keep IDs consistent across markdown and JSON.

Follow-up scheduling: whenever a finding or action needs a checkpoint, add `follow_up_trigger` plus a `due_date` to the finding entry, and use `follow_up_triggers` (array) plus `due_date` on the linked actions when multiple events apply. Triggers should be concrete (e.g., after merge of the related PR, next architecture review, before release, after compliance scan) so the review registry can mirror them.

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

## 5. Structural Gaps
- [F-1][G1] Gap statement — evidence/reference
- [F-2][G2] Gap statement — evidence/reference

## 6. Risk Areas
- [F-3][R1] Risk statement — severity/likelihood — rationale — linked gaps
- [F-4][R2] Risk statement — severity/likelihood — rationale — linked gaps

## 7. Recommendations
- [REC-1] Recommendation — mapped to gaps/risks with expected outcome — source findings [F-#]
- [REC-2] Recommendation — mapped to gaps/risks with expected outcome — source findings [F-#]

## 8. Priority Classification
- [REC-1] Priority: Critical | High | Medium | Low — rationale
- [REC-2] Priority: Critical | High | Medium | Low — rationale

## 9. Extracted Action Items
1. [A-1] Owner: TBD — Item — expected artifact — acceptance criteria — source [REC-#] — supports findings [F-#]
2. [A-2] Owner: TBD — Item — expected artifact — acceptance criteria — source [REC-#] — supports findings [F-#]

## 10. Blocking Items
- Blocking item 1 — condition to clear

## 11. Deferred Items
- Deferred item 1 — review trigger/condition
