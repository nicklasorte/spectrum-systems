# Pre-Claude Review Stabilization Report

Date: 2026-03-15

- **Artifact checks performed**: `node scripts/validate-review-artifacts.js` (passes, example pair aligned); `node scripts/ingest-claude-review.js --mode validate --schema design-reviews/claude-review.schema.json design-reviews/example-claude-review.actions.json` (passes); `pytest` after `python -m pip install -r requirements-dev.txt` (passes).
- **Canonical artifacts**: `design-reviews/example-claude-review.md` and `design-reviews/example-claude-review.actions.json` present with deterministic slug; JSON validates against `design-reviews/claude-review.schema.json` (schema_version 1.0.0), IDs and due_date fields align with markdown, no schema/example drift detected.
- **Documentation and validation flow**: Added ingest-validate command to `design-reviews/README.md`; local validation uses the commands above with `npm install --no-save --no-package-lock ajv@^8 ajv-formats@^2` plus dev Python deps; CI `review-artifact-validation.yml` runs Node validation and pytest on design-reviews changes; CI `claude-review-ingest.yml` validates changed `.actions.json` files before issue creation.
- **Cross-repo compliance scanner**: Example config at `governance/compliance-scans/scan-config.example.json`; run `node governance/compliance-scans/run-cross-repo-compliance.js <config>`; output format documented in `docs/cross-repo-compliance.md` and validated by `governance/compliance-scans/compliance-report.schema.json`.
- **Remaining gaps**: Mirroring follow-up triggers/due dates into `docs/review-registry.md` is still manual (no automation keeps registry in sync); the cross-repo compliance scanner is manual-only today and not wired into CI.
