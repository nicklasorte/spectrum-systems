# AGENTS.md — contracts/

## Ownership
Contract authority layer — this directory is the canonical source for all artifact schemas and interface contracts.
All downstream repos, modules, and engines import from here. They do not redefine or fork schemas locally.

## Local purpose
Publish and version JSON Schema contracts for all governed artifact types.
Maintain the `standards-manifest.json` as the single authoritative version registry.
Provide human-readable contract documentation in `contracts/docs/`.

## Constraints
- **Contract-first rule**: A schema must exist and be published here before any module implements against it.
- **No local overrides**: Downstream consumers may not redefine schemas. They import via `spectrum_systems.contracts.load_schema()`.
- **Version bump required**: Any breaking or additive change to a schema requires a version increment in both the schema file and `standards-manifest.json`.
- **Czar-level contracts**: `comment_resolution_matrix_spreadsheet_contract` preserves exact column headers and order. Do not reorder, rename, or add columns without an explicit PLAN prompt and stakeholder review.
- **No schema deletion**: Deprecated schemas are marked deprecated in the manifest, not removed.

## Required validation surface
Before any schema change is committed:
1. Run `pytest tests/test_contracts.py tests/test_contract_enforcement.py`.
2. Run `python scripts/run_contract_enforcement.py` and confirm no regressions.
3. Run `.codex/skills/contract-boundary-audit/run.sh` to detect downstream consumers that may be affected.
4. Update `contracts/standards-manifest.json` with the new version.

## Files that must not be changed casually
| File | Reason |
| --- | --- |
| `contracts/standards-manifest.json` | Version registry — every consumer pins to this |
| `contracts/schemas/artifact_envelope.schema.json` | Universal envelope — changing breaks all governed artifacts |
| `contracts/schemas/comment_resolution_matrix_spreadsheet_contract.schema.json` | Czar-level — fixed column headers, human-facing |
| `contracts/schemas/provenance_record.schema.json` | Shared provenance — changing breaks lineage tracking across all modules |

## Nearby files (read before editing)
- `contracts/schemas/` — all canonical schemas
- `contracts/examples/` — golden-path example payloads per contract
- `contracts/docs/` — human-readable contract documentation
- `contracts/standards-manifest.json` — published version registry
- `CONTRACTS.md` — contract consumption and authority rules
- `spectrum_systems/contracts/__init__.py` — programmatic contract loader
