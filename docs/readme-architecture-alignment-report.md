# README Architecture Alignment Report

## README claims confirmed by the repository
- The repo is the governance/control-plane: contracts, schemas, prompts, workflows, and eval standards live here while implementation code is downstream.
- Architecture reviews reside in `design-reviews/` with paired `.actions.json` files validated by `design-reviews/claude-review.schema.json`.
- Compliance guidance exists via `VALIDATION.md` and `docs/governance-conformance-checklist.md`.
- Ecosystem layering (system-factory → spectrum-systems → operational engines → spectrum-pipeline-engine → spectrum-program-advisor) is supported by `docs/ecosystem-architecture.md`, `docs/ecosystem-map.md`, and the system catalog in `SYSTEMS.md`.

## README claims that were outdated or unsupported
- The prior README pointed to `ecosystem/ecosystem-registry.json`, but no `ecosystem/` directory or registry JSON exists in the repository.

## Important repo components missing from the prior README
- Architecture Decision Records in `architecture-decisions/`.
- System catalog and per-system docs in `SYSTEMS.md`, `systems/`, `workflows/`, and `REPO_MAP.md`.
- Prompt governance (`prompts/`, `docs/prompt-standard.md`, `prompts/prompt-governance.md`) and rule packs in `rules/`.
- Evaluation assets and guidance in `eval/` and `evals/`.
- Contract and schema inventories (`contracts/`, `contracts/standards-manifest.json`, `schemas/README.md`).
- Review action tracking via `docs/review-actions/action-tracker-template.md` and `docs/review-registry.md`.
- Governance automation in `.github/workflows/` (artifact boundary check, Claude review ingest, project sync) and supporting scripts in `scripts/`.

## Links that were fixed
- Removed the broken `ecosystem/ecosystem-registry.json` reference and now point to `SYSTEMS.md`, `docs/system-map.md`, and `docs/system-status-registry.md` for ecosystem/status tracking.
- Added explicit links to review templates, action tracker, ADR template, contract manifest, prompt standards, and evaluation matrices.

## Structural decisions in the rewrite
- Adopted the canonical README layout (Overview, Purpose, Ecosystem Architecture, Governance Components, Key Directories, Review & Compliance Workflow, Documentation, Contributing).
- Added a key directory table to anchor navigation to actually present folders.
- Consolidated detailed explanations into existing docs to keep the README concise while highlighting automation and compliance touchpoints.

## Remaining ambiguities
- There is no machine-readable ecosystem registry file; ecosystem status is tracked in narrative docs (`SYSTEMS.md`, `docs/system-map.md`, `docs/system-status-registry.md`).
- Compliance execution beyond the artifact-boundary workflow relies on manual steps in `VALIDATION.md`; automated coverage for those checks is not defined in CI.
