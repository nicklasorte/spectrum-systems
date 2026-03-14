# Repository Metadata Contract

Standardized repository metadata keeps every spectrum-systems repo self-describing and auditable. The contract aligns repo identity, governance authority, and lifecycle status so downstream engines can reason about compatibility and conformance.

## Purpose
- Declare repository identity and role (`repo_name`, `repo_type`, `status`).
- Capture governance lineage (`governed_by`) and contract dependencies (`contracts_used`).
- Provide a maintainer contact for operational questions or escalations.
- Record the last architecture/design review date to surface review currency.

## Required fields (schema summary)
- `schema_version`: lock to `1.0.0`.
- `repo_name`: GitHub repo slug.
- `repo_type`: one of `constitution`, `engine`, `orchestrator`, `advisor`, `utility`.
- `description`: concise purpose statement.
- `governed_by`: governing repo or standards authority (usually `spectrum-systems`).
- `maintainer`: `{ "name": "...", "contact": "email or Slack handle" }`.
- `contracts_used`: array of contract/schema identifiers this repo implements or depends on.
- `last_architecture_review`: `YYYY-MM-DD` date for the most recent architecture/design review.
- `status`: one of `active`, `experimental`, `deprecated`.

## How to adopt in operational repos
1. Copy `docs/repository-metadata-template.json` to the operational repo root as `repository-metadata.json`.
2. Populate all required fields with repo-specific values and current review date.
3. Validate against `schemas/repository-metadata.schema.json` before opening PRs.
4. Keep `contracts_used` aligned with pinned contract versions and update `status` when lifecycle changes.

This repo remains the authoritative source for the metadata contract; downstream repos must not fork or redefine the schema.
