# Review Evidence Standard

Defines how findings and action items must link to proof before they can be considered closed. Use this standard across review artifacts, action trackers, and registry updates.

## Evidence link types
Use one or more of the following link types for each closed item:
- File path to the canonical artifact (`docs/...`, `contracts/...`, `schemas/...`)
- Test file or test run evidence (including command and result)
- Schema or contract reference (with version)
- CI workflow run or artifact URL
- GitHub issue or discussion reference
- Architecture Decision Record (ADR) entry

## Minimal closure language
Every closed item must record, at minimum:
- **Status** — e.g., Closed, Deferred, Open (with justification for non-closure).
- **Evidence** — direct link(s) to proof using the link types above.
- **Date** — closure or deferral date (YYYY-MM-DD).
- **Notes** — brief context, including trigger for deferred items or residual risk if partially mitigated.

## Valid closure rule
- “Done” without evidence is invalid. Closure requires at least one verifiable evidence link and the status/date/notes fields above.
- When a finding is deferred, record the trigger and expected follow-up window so future reviews can reconcile by ID.
- Record evidence in both the action tracker and the review registry entry so downstream reviewers can verify without re-locating proof.
