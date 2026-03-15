# Governance Manifest

Downstream repositories must declare a machine-readable `.spectrum-governance.json` so the ecosystem can deterministically enforce governance rules. The manifest records the system identity, repository type, upstream governance source, governance version, and pinned contract versions aligned to the standards manifest.

## Purpose
- Capture the canonical identity of every governed repository and bind it to the ecosystem registry.
- Declare contract dependencies as explicit version pins to prevent schema drift.
- Provide a uniform artifact for CI validation and cross-repo enforcement.
- Enable policy engines and dependency graphs to reason about compatibility across the ecosystem.

## Declaring contract dependencies
- Add a `.spectrum-governance.json` at the repository root that conforms to `governance/schemas/spectrum-governance.schema.json`.
- Pin every contract the repo consumes or emits. Versions must be semantic versions and must exist in `contracts/standards-manifest.json`.
- Set `governance_repo` to `spectrum-systems` and `governance_version` to the governance release being followed.
- Use the repository slug for `system_id` so it matches the entry in `ecosystem/ecosystem-registry.json`.

## Ecosystem enforcement
- CI validates manifests against the schema, the standards manifest, and the ecosystem registry to block unknown systems or undeclared contracts.
- Policy-as-code and the dependency graph consume manifests to detect drift and generate ecosystem-wide compatibility maps.
- The ecosystem registry marks systems with `manifest_required` so governance tooling knows which repos must publish manifests.

## Relationship to ecosystem registry and standards manifest
- `ecosystem/ecosystem-registry.json` is the authoritative list of systems; `system_id` in manifests must match a registry entry.
- `contracts/standards-manifest.json` is the authoritative list of contracts and versions; manifest contract pins must reference contracts defined there.
- Together, the registry, standards manifest, and governance manifests provide deterministic inputs for governance CI and policy evaluation.

## Canonical example
Place this file at the repository root as `.spectrum-governance.json`:

```json
{
  "system_id": "comment-resolution-engine",
  "repo_name": "comment-resolution-engine",
  "repo_type": "operational_engine",
  "governance_repo": "spectrum-systems",
  "governance_version": "1.0.0",
  "contracts": {
    "comment_resolution_matrix_spreadsheet_contract": "1.0.0",
    "comment_resolution_matrix": "1.0.0",
    "provenance_record": "1.0.0"
  }
}
```
