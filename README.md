# spectrum-systems

Governance/control-plane for the spectrum automation ecosystem. This repository defines the rules, contracts, schemas, prompts, workflows, and evaluation standards that downstream engines must follow; operational code lives in separate implementation repos.

## Overview
- Governing constitution for the czar repo org: publishes standards that system-factory scaffolds and downstream engines must consume.
- Maintains authoritative contracts, schemas, prompts, evaluation guidance, and governance workflows for spectrum systems.
- Holds review records, ADRs, and compliance automation; no production engines or proprietary data live here.

## Purpose
- Responsible for: artifact contracts and standards manifest, schema registry, prompt governance, evaluation and workflow standards, design reviews, ADRs, and ecosystem status registries.
- Not responsible for: operational engine implementations, runtime configs, or data pipelines (see downstream system repos for code).

## Ecosystem Architecture
See `docs/ecosystem-architecture.md` and `docs/ecosystem-map.md` for details. Current layers:
- system-factory scaffolds governed repos from templates.
- spectrum-systems (this repo) defines contracts, schemas, prompts, workflows, and governance rules.
- Operational engines (catalog in `SYSTEMS.md` and `systems/`) implement the governed interfaces.
- spectrum-pipeline-engine orchestrates workflows across engines.
- spectrum-program-advisor consumes readiness bundles to provide program guidance.

## Governance Components
- **Design reviews and actions**: `design-reviews/` holds review markdown and machine-readable actions validated by `design-reviews/claude-review.schema.json`; actions are tracked via `docs/review-actions/action-tracker-template.md` and registered in `docs/review-registry.md`. Actions may include scheduling metadata (`follow_up_trigger`, `due_date`) so registries and automation can set checkpoints. CI automatically validates pairing, schema alignment, finding IDs, and due_date format via `node scripts/validate-review-artifacts.js` in `.github/workflows/review-artifact-validation.yml`.
- **Architecture decisions**: ADRs live in `architecture-decisions/` using `architecture-decisions/adr-template.md`.
- **Artifact contracts and versioning**: `CONTRACTS.md`, `contracts/standards-manifest.json`, `contracts/schemas/`, and `CONTRACT_VERSIONING.md` define canonical inputs/outputs and compatibility rules.
- **Schema registry**: `schemas/` contains the authoritative schemas; inventory in `schemas/README.md`.
- **Prompt governance**: `prompts/` with standards in `docs/prompt-standard.md` and `prompts/prompt-governance.md`.
- **Evaluation framework**: per-system assets in `eval/` (matrix in `eval/test-matrix.md`) and dataset guidance in `evals/`.
- **Workflow definitions**: conceptual flows in `workflows/` and system overviews in `systems/`.
- **Rule packs**: governed rule sets (e.g., comment resolution) under `rules/`.
- **Compliance automation**: expectations in `VALIDATION.md` and `docs/governance-conformance-checklist.md`; `.github/workflows/artifact-boundary.yml` enforces `scripts/check_artifact_boundary.py`. Design-review ingestion is automated via `.github/workflows/claude-review-ingest.yml`, and issue project sync via `.github/workflows/ssos-project-automation.yml`.

## Key Directories
| Directory | Purpose |
| --- | --- |
| docs/ | Governance standards, ecosystem maps, lifecycle guides, review/action standards. |
| architecture-decisions/ | Accepted/proposed ADRs derived from design reviews. |
| design-reviews/ | Claude-led review artifacts plus machine-readable action files. |
| contracts/ | Artifact contracts, schemas, examples, and the standards manifest. |
| schemas/ | Canonical schema registry for governed artifacts. |
| prompts/ | Prompt catalog and governance notes. |
| systems/ | Per-system overviews, interfaces, designs, evaluations, prompts; index in `SYSTEMS.md`. |
| workflows/ | Conceptual workflow descriptions across systems. |
| eval/ | Evaluation harnesses per system and the coverage matrix. |
| evals/ | Shared evaluation dataset guidance, fixtures, and rubrics. |
| rules/ | Governed rule packs (e.g., comment-resolution rules). |
| examples/ | Illustrative artifacts and payload examples. |
| .github/workflows/ | Governance automation (artifact boundary, review ingest, project sync). |

## Review and Compliance Workflow
- Initiate architecture changes with a design review using `design-reviews/claude-review-template.md` and the sections in `docs/design-review-standard.md`; capture actions in the paired `.actions.json`, validate against the schema, and register in `docs/review-registry.md`.
- Convert accepted decisions into ADRs under `architecture-decisions/` and align updates with `contracts/standards-manifest.json` and schema changes.
- Downstream repos and PRs should run conformance checks in `VALIDATION.md` and `docs/governance-conformance-checklist.md`; the artifact boundary workflow enforces that only governed areas change when required.

## Claude Review Triage
- Apply the triage rule in `docs/governance-triage-rule.md` for new Claude findings: default to merging into canonical workstream buckets, reserve standalone issues for architecturally distinct items, and use labels such as `claude-review`, `workstream`, `standalone`, `duplicate`, `required-change`, or `optional-improvement` (see `docs/label-system.md`).

## Testing
- `pytest` validates governance artifacts and schemas, including registry completeness and review action examples.
- Run locally after installing dev dependencies:
  ```bash
  pip install -r requirements-dev.txt
  pytest
  ```

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
Downstream repositories can run compliance validation against the governance rules and contracts defined here to ensure alignment before adoption or release. See `VALIDATION.md`, `docs/governance-conformance-checklist.md`, and the cross-repo scanner in `docs/cross-repo-compliance.md`.

## Documentation
- Orientation: `REPO_MAP.md`, `SYSTEMS.md`, `docs/system-map.md`, `docs/system-status-registry.md`.
- Ecosystem: `docs/ecosystem-architecture.md`, `docs/ecosystem-map.md`, `docs/vision.md`.
- Standards: `CONTRACTS.md`, `CONTRACT_VERSIONING.md`, `docs/prompt-standard.md`, `prompts/README.md`.
- Governance: `docs/design-review-standard.md`, `design-reviews/claude-review-template.md`, `docs/review-actions/action-tracker-template.md`, `docs/review-registry.md`.
- Compliance: `VALIDATION.md`, `docs/governance-conformance-checklist.md`, `docs/implementation-boundary.md`.

## Contributing
Architecture, contract, or governance changes require a design review and action tracking before adoption. Keep ADRs, manifests, schemas, prompts, and evaluation assets in sync, and avoid adding operational engine code or data to this repository.
