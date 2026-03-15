# spectrum-systems

Constitutional governance/control-plane for the czar repo org. This repo defines the rules, contracts, schemas, prompts, workflows, and evaluation standards that downstream engines must follow; operational code lives in separate implementation repos.

## North Star Workflow
- Operating model with two interacting loops: **Coordination Loop** (roster → meetings → transcript → minutes → action items/FAQ → agenda/slides → next meeting) and **Document Production Loop** (**Engineering Tasks** → **Engineering Outputs** → working paper → review → adjudication → updated paper).
- The bridge is **Engineering Tasks** and **Engineering Outputs**, flowing between coordination and document production.
- See `docs/spectrum-study-operating-model.md` for the canonical operating model and ASCII loop diagram.

## Overview
- Publishes authoritative governance for system-factory scaffolds and downstream engines.
- Maintains contracts, schemas, prompts, evaluation guidance, design reviews, ADRs, and compliance automation.
- No production engines or proprietary data reside here.

## Purpose
- Governs artifact contracts and standards manifests, schema registry, prompt governance, evaluation standards, design reviews, ADRs, and ecosystem/state registries.
- Does not implement operational engines, runtime configs, or data pipelines; those live in downstream system repos.

## System Registry
The ecosystem maintains a canonical System Registry that records every governed repository, its role, loop alignment, maturity placement, and contract dependencies. See `docs/system-registry.md` for the control-plane catalog and machine-readable registry.

## Ecosystem Runtime Standard
This repository defines the canonical development environment for the ecosystem in `devcontainer-spec/`. Downstream engines, pipelines, and data lake tooling should inherit that devcontainer to ensure consistent Python 3.11 runtime and shared tooling across repos.

## Ecosystem Architecture
- Layers are detailed in `docs/ecosystem-architecture.md` and `docs/ecosystem-map.md`.
- system-factory scaffolds governed repos from templates.
- spectrum-systems (this repo) defines contracts, schemas, prompts, workflows, and governance rules.
- Operational engines (cataloged in `SYSTEMS.md`, `systems/`, and `ecosystem/ecosystem-registry.json`) implement governed interfaces.
- spectrum-pipeline-engine orchestrates workflows, and spectrum-program-advisor consumes readiness bundles for program guidance.

## Governance Components
- **Design reviews and actions**: `design-reviews/` holds review markdown and paired `.actions.json` files validated by `design-reviews/claude-review.schema.json`; actions register in `docs/review-registry.md` with the tracker template in `docs/review-actions/action-tracker-template.md`.
- **Architecture decisions**: ADRs live in `docs/adr/` using `docs/adr/ADR-TEMPLATE.md` (legacy ADRs remain in `architecture-decisions/`).
- **Artifact contracts and schema registry**: `CONTRACTS.md`, `CONTRACT_VERSIONING.md`, `contracts/standards-manifest.json`, `contracts/schemas/`, and `schemas/README.md` define canonical inputs/outputs and compatibility.
- **Prompt governance**: `prompts/` with standards in `docs/prompt-standard.md` and `prompts/prompt-governance.md`.
- **Evaluation framework**: per-system assets in `eval/` (coverage in `eval/test-matrix.md`) and shared guidance in `evals/`.
- **Ecosystem registry**: machine-readable registry in `ecosystem/ecosystem-registry.json` and schema; status and maps in `SYSTEMS.md`, `docs/system-map.md`, and `docs/system-status-registry.md`.
- **Rule packs and guidance**: governed rule sets under `rules/` with supporting governance docs in `docs/`.
- **Compliance automation**: conformance guidance in `VALIDATION.md` and `docs/governance-conformance-checklist.md`; cross-repo scanning in `docs/cross-repo-compliance.md` and `governance/compliance-scans/`; CI workflows in `.github/workflows/` with supporting scripts in `scripts/`.

## Architecture Governance
- The ecosystem uses the Three Horizons planning model (`docs/architecture-horizons.md`) to balance near-term execution, medium-term architecture, and long-term direction.
- Platform Inflection Points (`docs/platform-inflection-points.md`) mark structural shifts the ecosystem must cross.
- The Level 0-20 Maturity Model (`docs/system-maturity-model.md` and `docs/level-0-to-20-playbook.md`) guides evidence-backed progression.

## Architectural Decision Records
Major ecosystem architecture decisions are recorded as ADRs to preserve context, alternatives, and consequences. The canonical index and template live in `docs/adr/README.md`; new proposals should start from `docs/adr/ADR-TEMPLATE.md` and be referenced during Claude design reviews.

## Governance Artifact Rule
Governance artifacts (schemas, contracts, registry files, standards manifests) are platform dependencies and must be loaded from the local `spectrum-systems` checkout, not fetched over the network. See `docs/governance-artifact-loading-rule.md` for the full rule and rationale.

## Run Evidence Correlation Rule
All governed runs must emit a correlated evidence bundle (`run_manifest.json`, `evaluation_results.json`, `contract_validation_report.json`, and `provenance.json`) that shares a single `run_id`. Pipelines should reject or regenerate bundles when any artifact is missing or the `run_id` values diverge. See `docs/run-evidence-correlation-rule.md` for the full rule and rationale.

## System Maturity Model
The spectrum ecosystem advances along a Level 0-20 maturity ladder that charts the progression from concept to durable institutional infrastructure. The ladder and current ecosystem mapping live in `docs/system-maturity-model.md`.

## Maturity Framework and Playbook
- The ecosystem uses a Level 0-20 maturity model with evidence-based advancement.
- Claude reviews evaluate maturity explicitly using the rubric and refuse promotion without proof.
- See the canonical playbook in `docs/level-0-to-20-playbook.md` and the review rubric in `docs/review-maturity-rubric.md`.

## Long-Term Roadmap
The ecosystem maintains a maturity model, a playbook, and a canonical 100-step roadmap to guide long-range execution toward Level 20 maturity. See `docs/100-step-roadmap.md` for the roadmap and guardrails.

## Key Directories
| Directory | Purpose |
| --- | --- |
| docs/ | Governance standards, ecosystem maps, lifecycle guides, triage rules, registries. |
| docs/adr/ | ADR template and accepted ecosystem decision records integrated with Claude reviews. |
| design-reviews/ | Claude-led review artifacts plus machine-readable action files. |
| architecture-decisions/ | Legacy ADRs derived from design reviews (template included). |
| contracts/ | Artifact contracts, schema examples, and the standards manifest. |
| schemas/ | Canonical schema registry for governed artifacts. |
| prompts/ | Prompt catalog and governance notes. |
| eval/ | Evaluation harnesses per system and the coverage matrix. |
| evals/ | Shared evaluation dataset guidance, fixtures, and rubrics. |
| ecosystem/ | Machine-readable ecosystem registry and schema. |
| governance/ | Compliance scan configs and schemas (`governance/compliance-scans/`). |
| systems/ | Per-system overviews and interfaces; index in `SYSTEMS.md`. |
| workflows/ | Conceptual workflow descriptions across systems. |
| rules/ | Governed rule packs (e.g., comment-resolution rules). |
| examples/ | Illustrative artifacts and payload examples. |
| scripts/ | Validation and automation helpers for CI workflows. |
| .github/workflows/ | Governance automation (artifact boundary, review ingest, project sync, validation). |

## Review and Compliance Workflow
- Start architecture changes with `design-reviews/claude-review-template.md` aligned to `docs/design-review-standard.md`; pair markdown with `.actions.json` validated against `design-reviews/claude-review.schema.json` and register in `docs/review-registry.md`.
- Translate accepted decisions into ADRs under `architecture-decisions/` and keep contracts, schemas, prompts, and evaluation assets aligned with `contracts/standards-manifest.json` and `CONTRACT_VERSIONING.md`.
- Run conformance checks from `VALIDATION.md` and `docs/governance-conformance-checklist.md`; CI enforces review artifact validity (`.github/workflows/review-artifact-validation.yml`), artifact boundaries (`.github/workflows/artifact-boundary.yml`), review ingest, and project automation.
- Use `docs/cross-repo-compliance.md` and `governance/compliance-scans/scan-config.example.json` to guide cross-repo validation when coordinating downstream engines.

## Documentation
- Orientation and status: `REPO_MAP.md`, `SYSTEMS.md`, `docs/system-map.md`, `docs/system-status-registry.md`.
- Design reviews: `docs/design-review-standard.md`, `docs/review-to-action-standard.md`, `docs/design-review-culture.md`, `design-reviews/claude-review-template.md`, `docs/governance-triage-rule.md`, `docs/label-system.md`.
- Contracts and schemas: `CONTRACTS.md`, `CONTRACT_VERSIONING.md`, `contracts/standards-manifest.json`, `schemas/README.md`.
- Prompts and evaluations: `docs/prompt-standard.md`, `prompts/README.md`, `eval/README.md`, `eval/test-matrix.md`, `evals/evals-framework.md`.
- Compliance: `VALIDATION.md`, `docs/governance-conformance-checklist.md`, `docs/cross-repo-compliance.md`, `docs/implementation-boundary.md`.
- Vision and philosophy: `docs/vision.md`, `docs/system-philosophy.md`.

## Testing
- `pytest` validates governance artifacts, schemas, registries, and review action examples.
- Run locally after installing dev dependencies:
  ```bash
  pip install -r requirements-dev.txt
  pytest
  ```

## Contributing
Architecture, contract, or governance changes require a design review and action tracking before adoption. Keep ADRs, manifests, schemas, prompts, and evaluation assets in sync, maintain the ecosystem registry, and avoid adding operational engine code or data to this repository.
