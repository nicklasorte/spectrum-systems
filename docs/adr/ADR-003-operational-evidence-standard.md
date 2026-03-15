# Operational evidence standard

Status: Accepted

Date: 2026-03-15

## Context
Governed systems must prove that architecture, contracts, and maturity claims are backed by reproducible runs. Without a standard evidence bundle, reviews and automation would rely on narratives, making regressions invisible and blocking reliable promotion.

## Decision
Require every governed run to emit an evidence bundle containing `run_manifest.json`, `evaluation_results.json`, `contract_validation_report.json`, and `provenance.json`. Bundles must be produced by pipelines (not manual uploads) and stored alongside artifacts for downstream validation and review.

## Consequences
- Pipelines and engines must instrument runs to generate complete evidence bundles by default.
- Review, registry validation, and maturity promotion workflows treat missing or stale evidence as a high-severity finding.
- Evidence schemas become part of compatibility guarantees across systems and are validated in CI.
- Downstream advisory engines (e.g., spectrum-program-advisor) can consume consistent evidence to provide guidance.

## Alternatives considered
- Allowing manual summaries instead of machine-readable evidence, which would be unverifiable and brittle.
- Partial evidence (e.g., only evaluation outputs) without provenance or contract validation, which would hide integration risk.
- Per-system evidence formats, which would prevent shared validation and increase schema drift.

## Related artifacts
- `docs/operational-evidence-standard.md`
- `docs/review-evidence-standard.md`
- `docs/review-readiness-checklist.md`
- `docs/engine-governance-guidelines.md`
- `contracts/standards-manifest.json`
