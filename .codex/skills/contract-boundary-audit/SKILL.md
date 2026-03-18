# SKILL.md — contract-boundary-audit

## Metadata
- **Skill ID**: contract-boundary-audit
- **Type**: VALIDATE
- **Trigger**: Before any schema change is committed; at every checkpoint; after any WIRE step
- **Output**: Audit report listing contracts, their consumers, and any detected drift

## Purpose
Identify all modules and downstream repos that consume a given contract, and verify that:
1. They import from `spectrum_systems.contracts.load_schema()` — not local copies.
2. Their pinned version in the manifest matches the schema on disk.
3. No schema is defined locally in a module or downstream repo.

This audit enforces the contract-first and no-local-override rules from `AGENTS.md`.

## Inputs
- (Optional) `CONTRACT_NAME` — audit a specific contract. If omitted, audits all contracts.
- `contracts/schemas/` — canonical schema directory
- `contracts/standards-manifest.json` — version registry
- `spectrum_systems/` — module source tree to scan for local schema definitions

## Workflow

1. Load `contracts/standards-manifest.json` and enumerate all published contracts.

2. For each contract:
   a. Verify the schema file exists at `contracts/schemas/<name>.schema.json`.
   b. Verify the version in the manifest matches the `$schema` or `version` field in the schema file.
   c. Scan `spectrum_systems/` for any inline JSON Schema definitions (heuristic: look for `"$schema"` or `"type": "object"` with `"properties"` in .py files).
   d. Scan `spectrum_systems/` for direct file reads of `.schema.json` files that bypass `load_schema()`.

3. Identify consumers: grep `spectrum_systems/` and `scripts/` for `load_schema("<CONTRACT_NAME>")` or `validate_artifact(..., "<CONTRACT_NAME>")`.

4. Report:
   - Contracts with version mismatches.
   - Contracts with local overrides or inline definitions.
   - Contracts with no consumers (unused — may be stale).
   - Contracts with consumers that bypass `load_schema()`.

5. Exit non-zero if any violation is found.

## Usage
```bash
# Audit all contracts
.codex/skills/contract-boundary-audit/run.sh

# Audit a specific contract
.codex/skills/contract-boundary-audit/run.sh meeting_minutes_record
```

## Notes
- Run this before committing any schema change.
- Run this as part of every checkpoint bundle (called by `checkpoint-packager`).
- False positives (e.g., comments in code that mention schema field names) can be suppressed with `# audit-ignore` comments.
