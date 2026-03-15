# Cross-Repo Governance Compliance Scanner

The cross-repo compliance scanner provides a deterministic way for spectrum-systems to evaluate whether downstream repositories adhere to the constitutional governance rules. It runs entirely on local checkouts—no GitHub API calls or network access—and produces a machine-readable report for evidence and follow-up actions.

## What the scanner checks
- Required top-level governance files: `README.md`, `CLAUDE.md`, `CODEX.md`, `SYSTEMS.md`
- Required directories: `docs/`, `tests/`
- README reference to `spectrum-systems` (warning if missing)
- GitHub workflows presence (warning if `.github/workflows` is missing or empty)
- Repository path reachability (fails if the configured path does not exist)

## Configuration
Point the scanner at a JSON config listing the repos to inspect. Example: `governance/compliance-scans/scan-config.example.json`

```json
{
  "repos": [
    { "name": "comment-resolution-engine", "path": "../comment-resolution-engine" },
    { "name": "working-paper-review-engine", "path": "../working-paper-review-engine" }
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
      "compliant": true,
      "missing_requirements": [],
      "warnings": []
    },
    {
      "repo_name": "working-paper-review-engine",
      "repo_path": "/repos/working-paper-review-engine",
      "compliant": false,
      "missing_requirements": ["CLAUDE.md", "tests/"],
      "warnings": ["README missing reference to spectrum-systems", "GitHub workflows directory missing or empty"]
    }
  ]
}
```

Use any JSON Schema validator (e.g., `jsonschema` in Python) to verify reports against the schema if needed.
