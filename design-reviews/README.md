# Claude Design Reviews

This directory stores architecture and governance reviews produced by Claude Code in a format that can be consumed by GitHub automation.

Each review must include two artifacts that form a paired set:
1) Human-readable markdown: `YYYY-MM-DD-<slug>.md` using `design-reviews/claude-review-template.md` and the canonical sections in `docs/design-review-standard.md`.
2) Machine-readable actions JSON: `YYYY-MM-DD-<slug>.actions.json` validated against `design-reviews/claude-review.schema.json`.

Identifier alignment (markdown + JSON):
- Mint bracketed finding IDs `[F-1]`, `[F-2]`, `[F-3]`, … in the order findings first appear in the markdown. IDs are review-scoped and never renumbered after publication.
- Reuse those exact IDs as `findings[*].id` in the JSON actions file. Filenames and `review_metadata.review_id` must share the same slug so humans and automation can trace the pair.
- Keep secondary IDs stable and mapped back to findings: gaps `[G1]`, risks `[R1]`, recommendations `[REC-1]`, actions `[A-1]`, each citing the relevant `[F-#]`.
- Purpose: deterministic traceability for automation, issue generation, and future ingestion pipelines.
- Minimal alignment example: Markdown `[F-1] Deterministic IDs keep markdown and JSON aligned` ↔ JSON `"findings": [{"id": "F-1", "title": "Deterministic IDs keep markdown and JSON aligned", ...}]`

Workflow:
- Copy the template markdown and JSON schema to draft a new review; use deterministic filenames to preserve ordering.
- Populate findings, recommendations, and actions with stable IDs (`F-1`, `G1`, `R1`, `REC-1`, `A-1`) so automation can map them to GitHub issues and labels. `[F-#]` identifiers must exactly match between markdown and JSON.
- Capture scheduling metadata next to findings and actions: include `follow_up_trigger` (event checkpoint) and `due_date` (YYYY-MM-DD) when follow-up is required so registries and automation can schedule re-checks. Treat `follow_up_trigger` as the canonical event that should be mirrored into `docs/review-registry.md`; keep secondary events in `follow_up_triggers` when they help automation. All due dates must use `YYYY-MM-DD`.
- Validate both artifacts together:
  - Run `node scripts/validate-review-artifacts.js` to confirm every markdown review has a paired `.actions.json`, enforce schema validation, verify `[F-#]` identifiers align with JSON `findings[*].id`, and check due_date fields use `YYYY-MM-DD`.
  - Run `node scripts/ingest-claude-review.js --mode validate --schema design-reviews/claude-review.schema.json design-reviews/<review>.actions.json` to validate a specific actions JSON using the same schema the ingest workflow uses before creating issues.
  - (Optional) Run `python scripts/validate_review_alignment.py design-reviews/<review>.md design-reviews/<review>.actions.json` for a focused alignment check between a markdown/JSON pair.
- After publishing, register the review in `docs/review-registry.md` and follow `docs/review-to-action-standard.md` for tracker updates and follow-up triggers.
- CI enforcement: the `review-artifact-validation` workflow runs on pushes and pull requests that touch `design-reviews/**` and will block merges when schema validation, pairing, ID alignment, or due_date checks fail. Pytest also runs in the same workflow to keep the example artifacts healthy.

Examples:
- `design-reviews/example-claude-review.md`
- `design-reviews/example-claude-review.actions.json`
