# Governance Conformance Checklist

Use this checklist before releasing or updating an implementation repo. Every item must be satisfied for the release to be considered governed.

- [ ] `system_id` declared in repository metadata and documentation (matches `docs/implementation-boundary.md`).
- [ ] Target interface, schema, and contract versions pinned (from `contracts/standards-manifest.json` and system interface docs); rule/prompt set hashes recorded.
- [ ] Provenance coverage present for all material artifacts (inputs, outputs, manifests) and aligned to `docs/data-provenance-standard.md`.
- [ ] No local schema or contract redefinition; upstream artifacts are consumed and emitted exactly as published (no field renames/extensions).
- [ ] Evaluation harness executed with current fixtures; manifest includes date, commit, config, and results.
- [ ] External storage policy documented and enforced for operational data; manifests reference storage locations instead of embedding artifacts.
- [ ] Failure-mode handling aligned to `docs/system-failure-modes.md` with explicit block-and-surface behavior for invalid or missing inputs.
