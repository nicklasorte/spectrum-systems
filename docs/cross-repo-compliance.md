# Cross-Repo Governance Compliance Scanner

The cross-repo compliance scanner provides a deterministic way for spectrum-systems to evaluate whether downstream repositories adhere to the constitutional governance rules. It runs entirely on local checkouts—no GitHub API calls or network access—and produces a machine-readable report for evidence and follow-up actions.

## Phase 1 checks (governance identity + contract pins)
- Registry presence: repository must be listed in `ecosystem/ecosystem-registry.json` with correct `repo_name`, `layer`, `status`, and `contracts`.
- Governance manifest presence: `.spectrum-governance.json` must exist at repo root and validate against `governance/schemas/spectrum-governance.schema.json`.
- Identity alignment: manifest `system_id` must match the registry entry for the same `repo_name`.
- Contract pinning: manifest `contracts` keys must appear in `contracts/standards-manifest.json`, and the pinned versions must match published versions.
- Baseline hygiene (unchanged): required files (`README.md`, `CLAUDE.md`, `CODEX.md`, `SYSTEMS.md`), directories (`docs/`, `tests/`), README reference to spectrum-systems (warning), GitHub workflows presence (warning), repository path reachability.

## Configuration
Point the scanner at a JSON config listing the repos to inspect. Example: `governance/compliance-scans/scan-config.example.json`

```json
{
  "repos": [
    {
      "repo_name": "comment-resolution-engine",
      "repo_path": "../comment-resolution-engine",
      "expected_system_id": "SYS-001",
      "expected_repo_type": "operational_engine",
      "required_contracts": [
        "comment_resolution_matrix",
        "comment_resolution_matrix_spreadsheet_contract",
        "external_artifact_manifest",
        "meeting_agenda_contract",
        "pdf_anchored_docx_comment_injection_contract",
        "provenance_record",
        "reviewer_comment_set"
      ]
    },
    {
      "repo_name": "working-paper-review-engine",
      "repo_path": "../working-paper-review-engine",
      "expected_system_id": "SYS-007",
      "expected_repo_type": "operational_engine",
      "required_contracts": [
        "comment_resolution_matrix",
        "pdf_anchored_docx_comment_injection_contract",
        "provenance_record",
        "reviewer_comment_set",
        "working_paper_input"
      ]
    }
  ]
}
```

Paths can be relative to the current working directory or absolute.

## Running the scanner

```bash
node governance/compliance-scans/run-cross-repo-compliance.js governance/compliance-scans/scan-config.example.json
```

The scanner emits a JSON report to stdout. Redirect to a file if you want to persist the results.

## Output format
Reports follow `governance/compliance-scans/compliance-report.schema.json`.

```json
{
  "schema_version": "1.0.0",
  "scan_date": "2026-03-15",
  "repos": [
    {
      "repo_name": "comment-resolution-engine",
      "repo_path": "/repos/comment-resolution-engine",
      "expected_system_id": "SYS-001",
      "expected_repo_type": "operational_engine",
      "compliant": true,
      "missing_requirements": [],
      "failures": [],
      "warnings": []
    },
    {
      "repo_name": "working-paper-review-engine",
      "repo_path": "/repos/working-paper-review-engine",
      "expected_system_id": "SYS-007",
      "expected_repo_type": "operational_engine",
      "compliant": false,
      "missing_requirements": ["CLAUDE.md", "tests/"],
      "failures": [
        {
          "severity": "error",
          "type": "missing_governance_manifest",
          "repo": "working-paper-review-engine",
          "repo_path": "/repos/working-paper-review-engine"
        }
      ],
      "warnings": ["README missing reference to spectrum-systems", "GitHub workflows directory missing or empty"]
    }
  ]
}
```

Use any JSON Schema validator (e.g., `jsonschema` in Python) to verify reports against the schema if needed.
