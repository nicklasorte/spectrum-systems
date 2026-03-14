# GitHub Operations

Spectrum-systems is the governance and control-plane repository for SSOS GitHub operations across the czar organization. It anchors deterministic issue intake, labels, and automation so downstream repos stay aligned with the system contracts and schemas defined here.

## How the pieces fit together
- Issue templates (`.github/ISSUE_TEMPLATE/`) collect structured inputs that mirror SSOS contracts and keep triage consistent.
- Labels created by `scripts/setup-labels.sh` follow `docs/label-system.md` so filtering is deterministic across repositories.
- Workflows in `.github/workflows/` keep GitHub Projects in sync with issues; see `docs/github-project-automation.md` for required secrets and variables.
- Documentation in `docs/` (schema governance, provenance, lifecycle) sets the policy that templates, labels, and automation enforce.
- The `artifact-boundary` workflow plus `scripts/check_artifact_boundary.py` enforce the rule that operational data and binaries never enter GitHub; see `docs/data-boundary-governance.md` for the boundary policy.

## Running `scripts/setup-labels.sh`
Use the label bootstrap script to apply the standardized SSOS label set to this repo or any downstream repo:

```bash
./scripts/setup-labels.sh                # defaults to the current repo
./scripts/setup-labels.sh owner/name     # target a different repo
```

Prerequisites: GitHub CLI installed and authenticated (`gh auth login`). The script is idempotent and skips labels that already exist.

## GitHub Project automation
The `ssos-project-automation.yml` workflow syncs issues with the SSOS Project V2 board. Secrets and variables required by the workflow are listed in `docs/github-project-automation.md`, including how to fetch project and field IDs with `gh api`. Run the label script before enabling the workflow so issues land in the correct swimlanes.

## Manual GitHub UI Setup Still Required
- Repository description (see `docs/repo-metadata.md` for the recommended text)
- Repository website (leave blank unless a docs site is created later)
- Repository topics
- Project variables
- Project secrets
- Branch protection if desired

## Downstream inheritance
- Treat this repository as the source of truth for GitHub governance. Copy `.github/ISSUE_TEMPLATE/`, `.github/workflows/`, and `docs/label-system.md` into downstream repos.
- Run `scripts/setup-labels.sh` in each downstream repo to standardize labels.
- Apply the recommended metadata from `docs/repo-metadata.md` and configure secrets/variables per `docs/github-project-automation.md`.
- Keep updates centralized here first; downstream repos should only diverge when a documented exception is recorded in this control-plane repository.
