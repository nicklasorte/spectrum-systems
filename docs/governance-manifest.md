# Governance Manifest Standard

The spectrum governance manifest (`.spectrum-governance.json`) is the machine-readable identity card every governed repository publishes. It anchors a repo to the ecosystem registry, declares the contracts it consumes, and exposes upstream/downstream dependencies so the global dependency graph stays deterministic.

## Required fields
- `system_id` — system identifier issued in `ecosystem/ecosystem-registry.json`.
- `repo_name` — repository name.
- `repo_type` — category such as `operational_engine`, `advisory`, `template`, or `governance`.
- `governance_repo` — governance source (use `spectrum-systems` or the full slug `nicklasorte/spectrum-systems`).
- `governance_version` — semver of the governance baseline pinned by this repo.
- `contracts` — object mapping contract name to semver version.
- `upstream_systems` (optional) — array of `system_id` values that provide inputs to this system.
- `downstream_systems` (optional) — array of `system_id` values that consume this system’s outputs.

The canonical schema lives at `governance/schemas/spectrum-governance.schema.json` and enforces field types, semver versions, and identifier formats.

## Relationship to the ecosystem registry
`system_id`, `repo_name`, and `repo_type` must match the authoritative entries in `ecosystem/ecosystem-registry.json`. Manifests extend the registry by pinning contract versions and declaring graph edges, enabling spectrum-systems to assemble a global dependency graph without scraping downstream code.

## Pinning contracts
Downstream repositories must pin each consumed contract to the exact version published in `contracts/standards-manifest.json`. When a contract upgrades, downstream repos should:
1. Update their manifest contract pins.
2. Regenerate and review the dependency graph for compatibility.
3. Run local validation against the new schema version before promoting the change.

## Example manifest
```json
{
  "system_id": "SYS-001",
  "repo_name": "comment-resolution-engine",
  "repo_type": "operational_engine",
  "governance_repo": "spectrum-systems",
  "governance_version": "1.0.0",
  "contracts": {
    "comment_resolution_matrix": "1.0.0",
    "comment_resolution_matrix_spreadsheet_contract": "1.0.0",
    "provenance_record": "1.0.0"
  },
  "upstream_systems": [
    "SYS-007"
  ],
  "downstream_systems": [
    "SYS-009"
  ]
}
```

Use the schema validator in `tests/test_governance_manifest_schema.py` to confirm manifests stay aligned with governance rules.
