# Claude Design Reviews

This directory stores architecture and governance reviews produced by Claude Code in a format that can be consumed by GitHub automation.

Each review must include two artifacts that form a paired set:
1) Human-readable markdown: `YYYY-MM-DD-<slug>.md` using `design-reviews/claude-review-template.md` and the canonical sections in `docs/design-review-standard.md`.
2) Machine-readable actions JSON: `YYYY-MM-DD-<slug>.actions.json` validated against `design-reviews/claude-review.schema.json`.

- Deterministic finding IDs keep the pair aligned:
  - Review-scoped IDs reset per review: start at `[F-1]`, `[F-2]`, `[F-3]`, … in the order findings first appear in the markdown; treat every required change, recommended enhancement, or follow-up as a finding and do not renumber after publication.
  - Reuse those exact IDs as `findings[*].id` in the JSON actions file. The same slug should appear in both filenames and inside `review_metadata` to preserve traceability.
  - Keep secondary IDs stable and mapped back to findings: gaps `[G1]`, risks `[R1]`, recommendations `[REC-1]`, actions `[A-1]`.
  - Minimal example of aligned identifiers: Markdown `[F-1] Deterministic IDs keep markdown and JSON aligned` ↔ JSON `"findings": [{"id": "F-1", "title": "Deterministic IDs keep markdown and JSON aligned", ...}]`

Workflow:
- Copy the template markdown and JSON schema to draft a new review; use deterministic filenames to preserve ordering.
- Populate findings, recommendations, and actions with stable IDs (`F-1`, `G1`, `R1`, `REC-1`, `A-1`) so automation can map them to GitHub issues and labels. `[F-#]` identifiers must exactly match between markdown and JSON.
- Capture scheduling metadata next to findings and actions: include `follow_up_trigger` (event checkpoint) and `due_date` (YYYY-MM-DD) when follow-up is required so registries and automation can schedule re-checks. Treat `follow_up_trigger` as the canonical event that should be mirrored into `docs/review-registry.md`; keep secondary events in `follow_up_triggers` when they help automation.
- Validate both artifacts together: run `python scripts/validate_review_alignment.py design-reviews/<review>.md design-reviews/<review>.actions.json` to confirm `[F-#]` markers match the JSON `findings` IDs and to flag duplicate finding IDs in the JSON; then validate the JSON with `jsonschema` against `claude-review.schema.json`.
- After publishing, register the review in `docs/review-registry.md` and follow `docs/review-to-action-standard.md` for tracker updates and follow-up triggers.

Examples:
- `design-reviews/example-claude-review.md`
- `design-reviews/example-claude-review.actions.json`
