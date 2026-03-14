# Artifact Contracts

Spectrum Systems is the authoritative source for machine-readable artifact contracts that downstream implementation repos must consume. Contracts define the canonical input/output structures, required provenance metadata, and compatibility guarantees for spectrum engineering workflows.

## Why contracts live here
- This repo is the governing czar for the ecosystem; contracts must be published here before system-factory scaffolds them elsewhere.
- Downstream engines (e.g., Comment Resolution Engine, Working Paper Review Engine) import these contracts instead of redefining them.
- Changes to contracts follow the policies in `CONTRACT_VERSIONING.md` and are published through `contracts/standards-manifest.json`.

## How to consume contracts
- Use the JSON Schemas in `contracts/schemas/` as the single source of truth.
- Pull example payloads from `contracts/examples/` for fixtures and integration tests.
- Load schemas programmatically via `spectrum_systems.contracts.load_schema` and validate instances with `validate_artifact`.
- Track the standards release in `contracts/standards-manifest.json`; do not fork schema definitions in downstream repos.

## Contract inventory
- working_paper_input — structured intake for working paper revisions.
- reviewer_comment_set — normalized comment batches ready for resolution.
- comment_resolution_matrix — canonical mapping from comments to dispositions/actions.
- standards_manifest — registry of published contract versions and status.
- provenance_record — reusable provenance record for contract artifacts and runs.
