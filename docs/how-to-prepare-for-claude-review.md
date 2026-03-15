# How to Prepare for a Claude Review

Concise operator checklist to stage a clean, evidence-backed target before requesting a Claude governance or architecture review.

## Update before review
- Refresh `ecosystem/ecosystem-registry.json` and `contracts/standards-manifest.json` for currency and internal consistency.
- Ensure every review artifact in `docs/reviews/` has a paired tracker in `docs/review-actions/` and an entry in `docs/review-registry.md`.
- Validate contract and schema examples; regenerate any derived artifacts called out in the contracts.
- Capture boundary violations and mitigations in the tracker; do not leave them implicit.

## Gather evidence
- Link closure proof per `docs/review-evidence-standard.md` (files, tests, schemas, CI runs, issues, ADRs).
- Update action items with acceptance criteria, evidence placeholders, and blocking relationships.
- Stage proof links in the registry so follow-up reviews can reconcile by ID.

## Files Claude should inspect
- Latest review artifact and matching tracker for the scope under review.
- `docs/review-registry.md`, `docs/review-readiness-checklist.md`, and the relevant contract or schema files.
- Any CI workflows, test files, or ADRs cited as evidence.

## What not to ask Claude
- Do not ask Claude to locate missing evidence or restate incomplete actions; provide proof ahead of time.
- Do not request implementation planning inside this governance repo; direct implementation work to downstream engine repos.
- Avoid unbounded “find issues” prompts—arrive with reconciled prior findings and explicit questions.
