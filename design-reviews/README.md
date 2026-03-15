# Claude Design Reviews

This directory stores architecture and governance reviews produced by Claude Code in a format that can be consumed by GitHub automation.

Each review must include two artifacts that form a paired set:
1) Human-readable markdown: `YYYY-MM-DD-<slug>.md` using `design-reviews/claude-review-template.md` and the canonical sections in `docs/design-review-standard.md`.
2) Machine-readable actions JSON: `YYYY-MM-DD-<slug>.actions.json` validated against `design-reviews/claude-review.schema.json`.

Identifier discipline keeps the pair aligned:
- Findings are the anchor: tag every required change, optional improvement, or follow-up in markdown with a stable `[F-#]` (e.g., `[F-1]`) and reuse the exact same `id` values in the JSON `findings` array.
- Other IDs remain stable and linked: gaps `[G1]`, risks `[R1]`, recommendations `[REC-1]`, actions `[A-1]`. Cross-reference these to the relevant findings so automation can map everything back to `[F-#]`.
- Use the same slug for both filenames and record both paths under `review_metadata` to preserve traceability.

Workflow:
- Copy the template markdown and JSON schema to draft a new review; use deterministic filenames to preserve ordering.
- Extract findings, recommendations, and actions with stable IDs (`F-1`, `G1`, `R1`, `REC-1`, `A-1`) so automation can map them to GitHub issues and labels. `[F-#]` identifiers must exactly match between markdown and JSON.
- The root-level `findings` array in the JSON actions file drives issue generation. Each finding should include `recommended_action`, `files_affected`, `create_issue`, and `suggested_labels` so automation can file well-formed issues.
- Add scheduling metadata when relevant: `follow_up_trigger` (event such as after merge, before release, next architecture review, after compliance scan) and `due_date` (`YYYY-MM-DD`). These fields keep reviews actionable and can be mirrored into the review registry.
- Validate both artifacts together: run `python scripts/validate_review_alignment.py design-reviews/<review>.md design-reviews/<review>.actions.json` to confirm `[F-#]` markers match the JSON `findings` IDs, then validate the JSON with `jsonschema` against `claude-review.schema.json`.
- After publishing, register the review in `docs/review-registry.md` and follow `docs/review-to-action-standard.md` for tracker updates and follow-up triggers.

Examples:
- `design-reviews/example-claude-review.md`
- `design-reviews/example-claude-review.actions.json`
