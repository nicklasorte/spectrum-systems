# SSOS Project Automation Setup

This script configures the repository variables and secret required by `ssos-project-automation.yml` to sync issues with the SSOS GitHub Project.

## What the script does
- Queries the GitHub GraphQL API for the ProjectV2 ID, the `Lifecycle Stage` field ID, and the single-select option IDs for `Raw Evidence` and `Complete`.
- Writes the IDs to repository variables:
  - `SSOS_PROJECT_ID`
  - `SSOS_LIFECYCLE_FIELD_ID`
  - `SSOS_RAW_EVIDENCE_OPTION_ID`
  - `SSOS_COMPLETE_OPTION_ID`
- Sets the `PROJECT_TOKEN` repository secret from `PROJECT_TOKEN_VALUE` in your environment.
- Supports user-owned and org-owned projects, dry runs, and a verify mode that prints current variable values.

## Prerequisites
- GitHub CLI (`gh`) installed.
- `jq` installed.
- Authenticated with `gh auth login`.
- Exported token value: `export PROJECT_TOKEN_VALUE=<token-with-project-access>`.

## Usage
```bash
./scripts/setup-project-automation.sh
./scripts/setup-project-automation.sh --repo nicklasorte/spectrum-systems
./scripts/setup-project-automation.sh --owner nicklasorte --project-number 2
./scripts/setup-project-automation.sh --org my-org --project-number 2
./scripts/setup-project-automation.sh --dry-run
./scripts/setup-project-automation.sh --verify
```

Defaults: user owner `nicklasorte`, project number `2`, and the current repository. Use `--org` to target organization-owned projects; otherwise `--owner` is treated as a user login.

Dry-run prints the resolved IDs without writing variables or secrets. Verify prints the current repository variable values after setup. The `PROJECT_TOKEN` secret value is never echoed; it must be supplied via `PROJECT_TOKEN_VALUE`.

## Variables and secret created
- `PROJECT_TOKEN` (secret) — must already be in `PROJECT_TOKEN_VALUE`.
- `SSOS_PROJECT_ID`
- `SSOS_LIFECYCLE_FIELD_ID`
- `SSOS_RAW_EVIDENCE_OPTION_ID`
- `SSOS_COMPLETE_OPTION_ID`

## Troubleshooting
- Missing `gh`: install GitHub CLI and retry.
- Missing `jq`: install `jq` to parse GraphQL output.
- Not authenticated: run `gh auth login` with a token that can read issues and update the project.
- Project not found: confirm owner/org and project number; use `--owner` or `--org` accordingly.
- Field or option not found: ensure the project has a `Lifecycle Stage` single-select field with `Raw Evidence` and `Complete` options.
- Missing `PROJECT_TOKEN_VALUE`: export the token value before running the script.
- Insufficient token permissions: the token must access the target repo and project.

## Relation to SSOS automation
This setup populates the variables and secret consumed by `.github/workflows/ssos-project-automation.yml` so issues can be synced deterministically to the SSOS Project board.
