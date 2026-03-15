# Claude Design Reviews

This directory stores architecture and governance reviews produced by Claude Code in a format that can be consumed by GitHub automation.

Each review must include two artifacts:
1) Human-readable markdown: `YYYY-MM-DD-<slug>.md` using `design-reviews/claude-review-template.md` and the canonical sections in `docs/design-review-standard.md`.
2) Machine-readable actions JSON: `YYYY-MM-DD-<slug>.actions.json` validated against `design-reviews/claude-review.schema.json`. Keep identifiers (gaps, risks, recommendations, actions) in sync with the markdown.

JSON fields (required unless noted):
- `schema_version`: fixed to `1.0.0`.
- `review_metadata`: review identifiers, repository, scope, reviewer, source artifacts.
- `findings`: structured findings (`F-1`, `F-2`, ...) with severity/category/title/description plus optional automation routing (target_repo, labels, create_issue).
- `summary`: executive summary, gaps, risks (with IDs).
- `recommendations`: `REC-#` entries mapped to gaps/risks with priorities.
- `actions`: `A-#` automation-ready actions with targets, labels, acceptance criteria.
- `follow_up` (optional): next review date and triggers.

Workflow:
- Copy the template markdown and JSON schema to draft a new review; use deterministic filenames to preserve ordering.
- Extract recommendations and actions with stable IDs (`G1`, `R1`, `REC-1`, `A-1`) so automation can map them to GitHub issues and labels.
- After publishing, register the review in `docs/review-registry.md` and follow `docs/review-to-action-standard.md` for tracker updates and follow-up triggers.

Examples:
- `design-reviews/example-claude-review.md`
- `design-reviews/example-claude-review.actions.json`
