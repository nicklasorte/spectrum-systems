# Repository Map

## Purpose
Provide a quick orientation for humans and AI agents navigating the repository.

---

## Root-Level Files

- `README.md` — High-level description and full navigation index.
- `AGENTS.md` — AI agent roles, safe behavior rules, and ecosystem overview.
- `CLAUDE.md` — Guidance for Claude reasoning agents.
- `CLAUDE_REVIEW_PROTOCOL.md` — Protocol for Claude-led design reviews.
- `CODEX.md` — Guidance for Codex execution agents.
- `CONTRACTS.md` — Canonical artifact contracts and inter-system interface rules.
- `CONTRACT_VERSIONING.md` — Rules for versioning and breaking-change policy.
- `CONTRIBUTING.md` — Contribution guidelines and change workflow.
- `CHANGELOG.md` — Record of significant changes to governance artifacts.
- `DATA_SOURCES.md` — Authoritative list of data sources feeding the ecosystem.
- `DECISIONS.md` — Log of key architectural decisions.
- `GLOSSARY.md` — Shared vocabulary for the spectrum ecosystem.
- `REPO_MAP.md` — This file; quick-scan directory inventory.
- `SYSTEMS.md` — Central index and catalog of all governed automation systems.
- `SYSTEM_TEMPLATE.md` — Template for defining new systems.
- `VALIDATION.md` — Conformance checklist and how to run governance checks.
- `pytest.ini` — Pytest configuration for governance artifact tests.
- `requirements-dev.txt` — Python dev dependencies (install before running `pytest`).
- `run_study.py` — Top-level study runner script.

---

## Directories

### `systems/`
Per-system documentation. Each subfolder contains `overview.md`, `interface.md`, `design.md`, `evaluation.md`, and `prompts.md`.
- `comment-resolution/` — SYS-001: Comment reconciliation and disposition drafting engine.
- `transcript-to-issue/` — SYS-002: Issue and action extraction from meeting transcripts.
- `study-artifact-generator/` — SYS-003: Simulation output to structured study artifact.
- `spectrum-study-compiler/` — SYS-004: Packaging and validation of study deliverables.
- `spectrum-program-advisor/` — SYS-005: Decision readiness clarity for program governance.
- `meeting-minutes-engine/` — SYS-006: Structured meeting minutes from transcripts.
- `working-paper-review-engine/` — SYS-007: Comment intake and normalization for working papers.
- `docx-comment-injection-engine/` — SYS-008: Anchored DOCX comment injection.
- `spectrum-pipeline-engine/` — SYS-009: Orchestration across engines; emits run manifests.

### `docs/`
Architecture standards, ecosystem maps, lifecycle guides, triage rules, registries, and planning artifacts. Key files include:
- `vision.md` — North star and long-term direction.
- `system-philosophy.md` — Design principles for all governed systems.
- `system-interface-spec.md` — Interface contract standard every system must follow.
- `system-lifecycle.md` — Lifecycle stages from concept to production.
- `system-map.md` — Visual/textual map of systems and relationships.
- `docs/architecture/system_registry.md` — Canonical system registry for system names, ownership, and placeholder status.
- `system-status-registry.md` — Current maturity/status of each system.
- `system-failure-modes.md` — Known failure modes and mitigations.
- `system-maturity-model.md` — Level 0–20 maturity ladder definition.
- `level-0-to-20-playbook.md` — Evidence-based advancement playbook.
- `review-maturity-rubric.md` — Rubric used by Claude reviews to evaluate maturity.
- `100-step-roadmap.md` — Canonical long-range execution roadmap.
- `roadmap.md` — Near-term roadmap summary.
- `bottleneck-map.md` — Identified high-value leverage points in workflows.
- `data-lake-strategy.md` — Structured data foundation strategy.
- `data-provenance-standard.md` — Traceability model for all data and artifacts.
- `data-boundary-governance.md` — Governance rules for data boundaries.
- `reproducibility-standard.md` — Reproducibility requirements for governed runs.
- `data-class-registry.md` — Registry of data classes used across systems.
- `artifact-classification-standard.md` — How to classify governance artifacts.
- `artifact-envelope-standard.md` — Envelope format standard for artifacts.
- `artifact-chain.md` — Artifact flow and chaining rules across systems.
- `artifact-flow.md` — Diagram and description of end-to-end artifact flow.
- `contract-dependency-map.md` — Maps which systems depend on which contracts.
- `contract-versioning.md` — Contract versioning rules (doc form; canonical in `CONTRACT_VERSIONING.md`).
- `ecosystem-map.md` — Repo-level topology; how repositories relate.
- `ecosystem-architecture.md` — Layered architecture description.
- `ecosystem-dependency-graph.md` — Dependency graph narrative and guidance.
- `cross-repo-compliance.md` — Cross-repo compliance scanning guidance.
- `governance-conformance-checklist.md` — Step-by-step conformance checklist.
- `governance-enforcement-roadmap.md` — Plan for tightening governance enforcement.
- `governance-manifest.md` — Human-readable summary of the governance manifest.
- `governance-artifact-loading-rule.md` — Rule: load governance artifacts locally, not over the network.
- `governance-triage-rule.md` — Triage rules for labeling and routing governance issues.
- `label-system.md` — GitHub label taxonomy for issues and PRs.
- `implementation-boundary.md` — Defines what belongs in this repo vs. engine repos.
- `engine-governance-guidelines.md` — Guidelines downstream engine repos must follow.
- `engine-interface-standard.md` — Interface standard for operational engines.
- `design-review-standard.md` — Standard format for Claude-led design reviews.
- `design-review-culture.md` — Culture and expectations around design reviews.
- `review-to-action-standard.md` — How to extract and track actions from reviews.
- `review-registry.md` — Registry of all completed design reviews.
- `review-evidence-standard.md` — Evidence requirements for reviews.
- `review-readiness-checklist.md` — Checklist before triggering a Claude review.
- `how-to-prepare-for-claude-review.md` — Practical guide for review preparation.
- `pre-claude-review-stabilization-report.md` — Report capturing state before a major review.
- `prompt-standard.md` — Prompt authoring and governance standard.
- `run-evidence-correlation-rule.md` — Rule requiring correlated evidence bundles for governed runs.
- `operational-evidence-standard.md` — Standard for operational run evidence.
- `schema-governance.md` — Rules for authoring and evolving schemas.
- `provenance-checklist.md` — Checklist for provenance compliance.
- `provenance-implementation-guidance.md` — Guidance for implementing provenance in engines.
- `error-taxonomy.md` — Taxonomy of error types across the ecosystem.
- `ai-workflow-architecture.md` — Architecture of AI-assisted workflows.
- `agent-guidance-standard.md` — Standard for AI agent guidance files.
- `agent-selection-guide.md` — When to use Claude, Codex, or Copilot.
- `open-research-questions.md` — Design-phase unknowns requiring Claude reasoning.
- `cross-reference.md` — Cross-references between governance documents.
- `terminology.md` — Extended terminology and disambiguation notes.
- `house-method.md` — Domain-specific methodology reference.
- `spectrum-study-operating-model.md` — Canonical operating model with loop diagram.
- `comment-resolution-matrix-spreadsheet-contract.md` — Spreadsheet contract for comment resolution matrix.
- `system-planning-framework.md` — Framework for planning new systems.
- `system-planning-steps.md` — Step-by-step system planning guide.
- `system-architecture.md` — Architectural patterns for systems in the ecosystem.
- `architecture-horizons.md` — Three Horizons planning model.
- `platform-inflection-points.md` — Structural shifts the ecosystem must cross.
- `policy-as-code.md` — Vision for policy-as-code enforcement.
- `doc-governance.md` — Documentation governance rules.
- `repo-maintenance-checklist.md` — Checklist for keeping the repo healthy.
- `new-repo-checklist.md` — Checklist when spinning up a new downstream repo.
- `repository-metadata.md` — Repository metadata guidelines.
- `repo-metadata.md` — Repo metadata reference.
- `readme-architecture-alignment-report.md` — Report on README ↔ architecture alignment.
- `github-operations.md` — GitHub operations playbook.
- `github-project-automation.md` — GitHub Projects automation guidance.
- `project-automation-setup.md` — Setup guide for GitHub project automation.
- `external-storage-implementation-guide.md` — Guide for external storage integration.
- `step1-high-value-bottlenecks.md` — Initial bottleneck analysis.
- `adr/` — Accepted Architecture Decision Records (ADRs) and template.
- `review-actions/` — Action tracker stubs paired to design reviews.
- `reviews/` — Supplementary review notes and artifacts.
- `roadmaps/` — Additional roadmap artifacts.

### `schemas/`
Authoritative schema definitions for governed artifacts.
- `comment-schema.json` — Schema for comment objects.
- `issue-schema.json` — Schema for extracted issues/actions.
- `provenance-schema.json` — Schema for provenance metadata.
- `study-output-schema.json` — Schema for study output artifacts.
- `assumption-schema.json` — Schema for assumption records.
- `compiler-manifest.schema.json` — Schema for study compiler manifests.
- `artifact-bundle.schema.json` — Schema for artifact bundle packaging.
- `diagnostics.schema.json` — Schema for diagnostic outputs.
- `precedent-schema.json` — Schema for precedent records.
- `repository-metadata.schema.json` — Schema for repo metadata files.
- `data-lake/` — Extended, provenance-complete schemas for data lake use.
- `README.md` — Schema inventory and guidance.

### `contracts/`
Artifact contracts, schema examples, and the standards manifest.
- `standards-manifest.json` — Canonical contract versions all engines must pin to.
- `meeting_minutes_contract.yaml` — Contract governing meeting minutes artifact shape.
- `artifact-contracts.md` — Human-readable artifact contract descriptions.
- `artifact-class-registry.json` — Registry of artifact classes.
- `comment-resolution-matrix.schema.json` — Schema for the comment resolution matrix.
- `meeting-minutes.schema.json` — Schema for meeting minutes artifacts.
- `review-output.schema.json` — Schema for review output artifacts.
- `schemas/` — Contract-layer schemas for cross-engine interfaces.
- `examples/` — Example payloads illustrating contract shapes.
- `docs/` — Contract-specific documentation (e.g., meeting agenda contract).

### `prompts/`
Prompt catalog aligned to governed systems.
- `comment-resolution.md` — Prompts for SYS-001.
- `transcript-to-issue.md` — Prompts for SYS-002.
- `report-drafting.md` — Prompts for SYS-003/004 report drafting.
- `spectrum-study-compiler.md` — Prompts for SYS-004.
- `prompt-governance.md` — Prompt authoring and versioning rules.
- `prompt-template.md` — Template for new prompts.
- `prompt-versioning.md` — Versioning policy for prompts.
- `README.md` — Prompt index.

### `eval/`
Evaluation harness scaffolds per system.
- `test-matrix.md` — Coverage matrix mapping systems to evaluation assets.
- `benchmark-definition.md` — Benchmark definitions and scoring guidance.
- `comment-resolution/` — Eval assets for SYS-001.
- `transcript-to-issue/` — Eval assets for SYS-002.
- `study-artifacts/` — Eval assets for SYS-003.
- `spectrum-study-compiler/` — Eval assets for SYS-004.
- `README.md` — Evaluation framework overview.

### `evals/`
Shared evaluation datasets, fixtures, and rubrics.
- `evals-framework.md` — Shared evaluation framework guidance.
- `fixtures/` — Shared test fixtures.
- `rubrics/` — Shared evaluation rubrics.

### `ecosystem/`
Machine-readable registries and trackers.
- `ecosystem-registry.json` — Authoritative registry of all repos and systems.
- `ecosystem-registry.schema.json` — Schema for the ecosystem registry.
- `system-registry.json` — System-level registry with maturity and contract info.
- `system-registry.schema.json` — Schema for the system registry.
- `dependency-graph.json` — Machine-readable dependency graph.
- `dependency-graph.schema.json` — Schema for the dependency graph.
- `maturity-tracker.json` — Current maturity levels per system.
- `maturity-tracker.schema.json` — Schema for the maturity tracker.
- `roadmap-tracker.json` — Roadmap item tracking.
- `roadmap-tracker.schema.json` — Schema for the roadmap tracker.

### `design-reviews/`
Claude-led design review artifacts.
- `claude-review-template.md` — Template for new design reviews.
- `claude-review.schema.json` — JSON schema validating `.actions.json` files.
- `example-claude-review.md` — Example completed review.
- `example-claude-review.actions.json` — Example machine-readable actions file.
- `2026-03-15-governance-architecture-audit.md` — Governance architecture audit review.
- `2026-03-15-governance-architecture-audit.actions.json` — Actions from the audit.
- `devcontainer/` — Devcontainer-related review artifacts.
- `README.md` — Design review workflow guidance.

### `architecture-decisions/`
Legacy Architecture Decision Records (ADRs) derived from design reviews. New ADRs go in `docs/adr/`.

### `governance/`
Compliance scanning configuration and policy schemas.
- `compliance-scans/` — Scan configs and outputs.
- `policies/` — Governance policy definitions.
- `examples/` — Example compliance scan configurations.
- `schemas/` — Schemas for governance artifacts.
- `work-items/` — Canonical work items generated from review artifacts (Prompt K). Contains `work-items.json` (machine-readable) and `work-items-summary.md` (human-readable).
- `repo-compliance.schema.json` — Schema for repo compliance reports.
- `scan-config.example.json` — Example scan configuration.

### `rules/`
Governed rule packs used by automation systems.
- `comment-resolution/` — Rules governing comment resolution behavior.

### `workflows/`
Conceptual workflow descriptions across systems and loops.

### `issues/`
Implementation backlog items (Codex/Copilot tasks). Design-phase unknowns belong in `docs/open-research-questions.md`.

### `examples/`
Illustrative artifacts and payload examples demonstrating contract shapes.

### `artifacts/`
Generated or reference artifacts used in governance and evaluation.

### `scripts/`
Validation and automation helpers used by CI workflows.
- `check_artifact_boundary.py` — Validates no production code crosses into this repo.
- `check_review_registry.py` — Checks review registry completeness.
- `generate_work_items.py` — Generates canonical work items from review artifacts (Prompt K).
- `validate_governance_manifest.py` — Validates `contracts/standards-manifest.json`.
- `validate_review_alignment.py` — Validates review-to-action alignment.
- `validate_review_artifacts.js` — JS validator for review artifact schema.
- `validate_run_evidence_bundle.py` — Validates run evidence bundle correlation.
- `ingest-claude-review.js` — Ingests a completed Claude review into the registry.
- `build_dependency_graph.py` — Builds the machine-readable dependency graph.
- `generate_dependency_graph.py` — Generates dependency graph artifacts.
- `update_readme_mental_map.py` — Updates the README mental map section.
- `setup-labels.sh` — Sets up GitHub issue labels.
- `setup-project-automation.sh` — Sets up GitHub Projects automation.

### `spectrum_systems/`
Python package root for governance tooling used by `pytest` and scripts.

### `tests/`
`pytest` test suite validating governance artifacts, schemas, registries, and review action examples.

### `.github/workflows/`
CI automation enforcing governance rules.
- `artifact-boundary.yml` — Blocks production code from entering this repo.
- `review-artifact-validation.yml` — Validates design review artifacts against schema.
- `review-ingest.yml` — Automates ingestion of Claude review outputs.
- `project-sync.yml` — Syncs issues/PRs with GitHub Projects.

### `devcontainer-spec/`
Canonical devcontainer definition for the ecosystem. Downstream engine repos should inherit this to ensure a consistent Python 3.11 runtime.

### `.devcontainer/`
Local devcontainer configuration for this repository.

---

## Key Entry Points

| Goal | Start here |
| --- | --- |
| Understand the repo | `README.md` |
| Find a system | `SYSTEMS.md` → `systems/<system>/overview.md` |
| Understand contracts | `CONTRACTS.md`, `contracts/standards-manifest.json` |
| Find schemas | `schemas/README.md` |
| Find prompts | `prompts/README.md` |
| Run evaluations | `eval/test-matrix.md` |
| Review governance | `VALIDATION.md`, `docs/governance-conformance-checklist.md` |
| Understand the ecosystem | `docs/ecosystem-map.md`, `ecosystem/ecosystem-registry.json` |
| Design reviews | `design-reviews/claude-review-template.md` |
| ADRs | `docs/adr/README.md` |
| Maturity model | `docs/system-maturity-model.md`, `docs/level-0-to-20-playbook.md` |
| Roadmap | `docs/100-step-roadmap.md` |
