# Claude Design Reviews

Claude reviews are automation-ready only when a **paired artifact set** is present and valid:
- Human-readable markdown: `design-reviews/YYYY-MM-DD-<slug>.md` using `design-reviews/claude-review-template.md` and the canonical sections in `docs/design-review-standard.md`.
- Machine-readable actions JSON: `design-reviews/YYYY-MM-DD-<slug>.actions.json` that **must** validate against `design-reviews/claude-review.schema.json`.

Pairing and naming rules:
- The slug is the single source of identity: `review_id`, markdown filename, and actions filename must all match (`YYYY-MM-DD-<slug>`).
- Record both artifact paths in `review_metadata.source_artifact` and `review_metadata.actions_artifact`.
- Downstream issue creation depends on the JSON actions file; a markdown-only review is **not publishable** for automation.

Identifier discipline keeps the pair aligned:
- Findings are the anchor: tag every required change, optional improvement, or follow-up in markdown with a stable `[F-#]` (e.g., `[F-1]`) and reuse the exact same `id` values in the JSON `findings` array.
- Other IDs remain stable and linked: gaps `[G1]`, risks `[R1]`, recommendations `[REC-1]`, actions `[A-1]`. Cross-reference these to the relevant findings so automation can map everything back to `[F-#]`.

Workflow gates:
- Copy the template markdown and JSON schema to draft a new review; keep deterministic filenames to preserve ordering.
- Extract findings, recommendations, and actions with stable IDs (`F-1`, `G1`, `R1`, `REC-1`, `A-1`) so automation can map them to GitHub issues and labels. `[F-#]` identifiers must exactly match between markdown and JSON.
- Validate both artifacts together **before publishing**:
  - Alignment: `python scripts/validate_review_alignment.py design-reviews/YYYY-MM-DD-<slug>.md design-reviews/YYYY-MM-DD-<slug>.actions.json`
  - Schema: `node scripts/ingest-claude-review.js --mode validate --schema design-reviews/claude-review.schema.json design-reviews/YYYY-MM-DD-<slug>.actions.json`
- After publishing, register the review in `docs/review-registry.md` and follow `docs/review-to-action-standard.md` for tracker updates and follow-up triggers.

Examples:
- `design-reviews/2026-03-14-claude-review-automation.md`
- `design-reviews/2026-03-14-claude-review-automation.actions.json`
