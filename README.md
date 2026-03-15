# spectrum-systems

Governance/control-plane for spectrum automation systems. This repo defines architecture standards, contracts, schemas, prompts, workflows, and evaluation rules; implementation code lives in downstream engines.

## Overview
This repository serves as the governing constitution for the spectrum ecosystem, setting the rules, contracts, and lifecycle gates for systems scaffolded from system-factory and operated by downstream engines.

## Ecosystem Architecture
- Layer 1 — system-factory: scaffolds new repositories from governed templates.
- Layer 2 — spectrum-systems: control plane for governance rules, contracts, schemas, prompts, workflows, and standards manifests.
- Layer 3 — Operational Engines: implement the governed rules (e.g., working-paper-review-engine, comment-resolution-engine, meeting-minutes-engine, docx-comment-injection-engine).
- Layer 4 — Orchestration: spectrum-pipeline-engine coordinates workflows across engines.
- Layer 5 — Program Intelligence: spectrum-program-advisor analyzes artifacts and provides program guidance.

## Governance Framework
`spectrum-systems` defines:
- artifact contracts and standards manifests for downstream engines
- schema standards and prompt governance
- architecture review protocols and action tracking
- the ecosystem registry of governed repositories
- compliance validation expectations for operational repos

## Architecture Reviews
Architecture reviews are stored under `design-reviews/`. Claude-led reviews produce both a markdown review artifact and a machine-readable JSON actions file aligned to `design-reviews/claude-review.schema.json`.

## Testing
- `pytest` validates governance artifacts and schemas, including registry completeness and review action examples.
- Run locally with: `pytest`

## Design Review Framework
- Canonical format: `docs/design-review-standard.md`
- Review-to-action flow: `docs/review-to-action-standard.md`
- Immutable artifacts directory: `docs/reviews/`
- Action trackers and template: `docs/review-actions/` and `docs/review-actions/action-tracker-template.md`
- Registry of reviews: `docs/review-registry.md`
- Culture and rationale: `docs/design-review-culture.md`
- Architecture decisions derived from reviews are captured as ADRs in `architecture-decisions/` using `architecture-decisions/adr-template.md`.
## Ecosystem Registry
The ecosystem registry tracks all repositories participating in the spectrum ecosystem and their governance state. See `docs/systems-registry.md`; the JSON registry reference is `ecosystem/ecosystem-registry.json`.

## Repository Compliance
Downstream repositories can run compliance validation against the governance rules and contracts defined here to ensure alignment before adoption or release. See `VALIDATION.md` and `docs/governance-conformance-checklist.md`.

## Documentation
- `docs/ecosystem-architecture.md`
- `docs/contract-versioning.md`
- `docs/governance-conformance-checklist.md`

## Contribution
Changes to governance rules, contracts, or architecture standards require an architecture review before adoption. Follow `docs/design-review-standard.md` and capture resulting actions using `docs/review-actions/action-tracker-template.md`.
