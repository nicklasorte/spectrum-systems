# Governance Manifest Standard

Downstream repositories must publish a machine-readable `.spectrum-governance.json` at their root to declare how they are governed by `spectrum-systems`. This manifest is the Phase 1 enforcement unit for registry presence, contract pinning, and identity checks.

## Required fields
- `system_id`: Governing system identifier (e.g., `SYS-001`).
- `governance_repo`: Repository slug that publishes governance (e.g., `nicklasorte/spectrum-systems`).
- `governance_version`: Published governance release that the repo pins to (semver or calendar version).
- `contracts`: Object mapping `contract_name` → pinned version string (semver); must be non-empty.

Manifests must conform to `governance/schemas/spectrum-governance.schema.json`.

## Example: comment-resolution-engine
```json
{
  "system_id": "SYS-001",
  "governance_repo": "nicklasorte/spectrum-systems",
  "governance_version": "2026.03.0",
  "contracts": {
    "comment_resolution_matrix": "1.0.0",
    "comment_resolution_matrix_spreadsheet_contract": "1.0.0",
    "external_artifact_manifest": "1.0.0",
    "meeting_agenda_contract": "1.0.0",
    "pdf_anchored_docx_comment_injection_contract": "1.0.1",
    "provenance_record": "1.0.0",
    "reviewer_comment_set": "1.0.0"
  }
}
```
