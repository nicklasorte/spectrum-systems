# Claude Design Reviews

This directory stores architecture and governance reviews produced by Claude Code in a format that can be consumed by GitHub automation. **Automation-ready reviews are only considered publishable when the markdown and JSON actions artifacts are present as a validated pair.**

Each review must include two artifacts with matching stems:
1) Human-readable markdown: `YYYY-MM-DD-<slug>.md` using `design-reviews/claude-review-template.md` and the canonical sections in `docs/design-review-standard.md`.
2) Machine-readable actions JSON: `YYYY-MM-DD-<slug>.actions.json` validated against `design-reviews/claude-review.schema.json`. Keep identifiers (gaps, risks, recommendations, actions, findings) in sync with the markdown.

Required pairing and validation:
- The actions artifact path must be recorded in `review_metadata.actions_artifact`, and the markdown path must be recorded in `review_metadata.source_artifact`.
- Naming must stay aligned: `design-reviews/YYYY-MM-DD-<slug>.md` pairs with `design-reviews/YYYY-MM-DD-<slug>.actions.json`.
- Validate before publishing: `node scripts/ingest-claude-review.js --mode validate --schema design-reviews/claude-review.schema.json design-reviews/YYYY-MM-DD-<slug>.actions.json`.

Workflow:
- Copy the template markdown and JSON schema to draft a new review; use deterministic filenames to preserve ordering.
- Extract findings, recommendations, and actions with stable IDs (`F-1`, `G1`, `R1`, `REC-1`, `A-1`) so automation can map them to GitHub issues and labels.
- The root-level `findings` array in the JSON actions file drives issue generation. Each finding should include `recommended_action`, `files_affected`, `create_issue`, and `suggested_labels` so automation can file well-formed issues.
- After publishing, register the review in `docs/review-registry.md` and follow `docs/review-to-action-standard.md` for tracker updates and follow-up triggers.

Examples:
- `design-reviews/2026-03-14-claude-review-automation.md`
- `design-reviews/2026-03-14-claude-review-automation.actions.json`
