# CODEX.md

Codex Agent Guide for Spectrum Systems

---------------------------------------------------------------------

# Purpose

This document provides instructions for Codex-style agents interacting with repositories derived from the Spectrum Systems architecture.

Codex agents should treat this repository and its descendants as **structured engineering systems**, not generic software projects.

The goal is to maintain consistent repository structure, reproducibility, and traceability.

---------------------------------------------------------------------

# Codex Responsibilities

Codex should primarily be used for repository-level tasks such as:

- creating directories
- generating documentation
- generating schemas
- updating multiple files
- restructuring repository layout
- applying structured instructions
- expanding planning artifacts
- scaffolding workflows

Codex acts as a **repository execution engine**.

---------------------------------------------------------------------

# Tasks Codex Should Perform

Codex should be used for tasks such as:

Repository creation  
Directory restructuring  
Bulk documentation generation  
Schema creation  
Applying structured change instructions  
Updating multiple documents  
Creating workflow templates  
Updating registry files  

Codex is the preferred agent when changes involve **multiple files or repository structure**.

## Design review follow-up
- Consume review action trackers from `docs/review-actions/` and update related governance artifacts deterministically.
- Do not generate automation code in this repo; focus on standards, registries, and documentation specified by the review outputs.
- When implementing follow-ups, preserve the canonical structures in `docs/design-review-standard.md`, `docs/review-to-action-standard.md`, and `docs/review-registry.md`.

---------------------------------------------------------------------

# Tasks Codex Should Avoid

Codex should NOT:

- design architecture from scratch
- invent new conceptual frameworks
- perform large reasoning tasks
- implement complex code logic

Those tasks should be handled by reasoning agents such as Claude.

---------------------------------------------------------------------

# Interaction With Other Agents

Development should follow this workflow:

Claude → reasoning and design  
Codex → repository updates  
Copilot → code implementation

Codex should assume design decisions already exist before making structural changes.

---------------------------------------------------------------------

# Repository Modification Principles

When modifying repositories derived from this architecture, Codex should follow these principles:

1. Maintain documentation-first structure.
2. Avoid introducing production code into design repositories.
3. Preserve conceptual links between documents.
4. Maintain schema consistency.
5. Preserve provenance metadata fields.

---------------------------------------------------------------------

# Schema Creation Guidance

When generating schemas, Codex should:

- include provenance metadata fields
- follow the data provenance standard
- keep schemas human-readable
- avoid unnecessary complexity

Reference:

docs/data-provenance-standard.md

---------------------------------------------------------------------

# Multi-File Update Guidance

When performing large updates, Codex should:

- maintain existing directory structure
- update references between documents
- verify links remain valid
- avoid duplicating concepts across files

---------------------------------------------------------------------

# Derived Repository Expectations

All implementation repositories derived from this lab notebook should include:

CLAUDE.md  
CODEX.md  

These files help AI agents understand how to interact with the repository.

---------------------------------------------------------------------

## Roadmap Execution Rule

- Only the authoritative roadmap may be used for implementation
- The authoritative roadmap is:
  docs/roadmaps/system_roadmap.md
- Subordinate roadmap documents provide context only and must not drive execution
- DEPRECATED documents must not be used

---------------------------------------------------------------------

## Strategy and source authority enforcement
- Treat `docs/architecture/system_strategy.md` as governing law for roadmap/review/progression artifacts.
- Treat `docs/architecture/system_source_index.md` as mandatory bounded grounding input (not optional reference).
- When generating roadmap/review/progression artifacts, include explicit provenance fields for strategy and sources.
- Reject changes that introduce duplicate governance surfaces for roadmap generation, review standards, control gating, certification, policy lifecycle, or observability.
