# Cross-Repo Contract Enforcement

This document explains how the spectrum-systems governance architecture validates
contract usage across the governed ecosystem.

## Overview

Cross-repo contract enforcement ensures that every governed repository declares
contracts that actually exist in the canonical standards manifest, pins the correct
versions, and behaves consistently with the consumer/producer relationships declared
in that manifest.

The enforcement is **repo-local, deterministic, and requires no external network
calls**. All inputs are files that live in this repository:

| Input | Purpose |
|---|---|
| `contracts/standards-manifest.json` | Canonical source of truth for all contracts and their versions |
| `ecosystem/ecosystem-registry.json` | Registry of all governed repos and their metadata |
| `governance/examples/manifests/*.spectrum-governance.json` | Per-repo governance manifests with contract pins |

## How Enforcement Works

### Script

```
scripts/run_contract_enforcement.py
```

Run it locally:

```bash
python scripts/run_contract_enforcement.py
```

Exit code `0` = no enforcement failures (warnings are allowed).
Exit code `1` = one or more hard enforcement failures.

### Enforcement Rules

| Rule | Severity | Description |
|---|---|---|
| `contract-exists` | **failure** | A contract pin in a governance manifest references an `artifact_type` that does not exist in `contracts/standards-manifest.json`. |
| `version-pin` | **failure** | A pinned contract version does not match the `schema_version` in the canonical standards manifest. Exact version match is required. |
| `consumer-consistency` | warning | A repo is listed as an `intended_consumer` of a contract in the standards manifest but does not declare that contract in its governance manifest. |

### What Counts as a Failure vs. a Warning

**CI fails** (`exit 1`) when:
- Any governed repo declares a contract that does not exist in the standards manifest (`contract-exists`).
- Any governed repo pins a contract at a version that differs from the canonical version (`version-pin`).

**CI does not fail** for:
- Consumer consistency gaps — these are surfaced as warnings and listed in the enforcement report.
- Not-yet-enforceable repos — reported clearly but not blocked.

### Not-Yet-Enforceable Repos

A repo is classified as **not-yet-enforceable** when:
- It appears in `ecosystem/ecosystem-registry.json` with `manifest_required: true`.
- It does not yet have a governance manifest under `governance/examples/manifests/`.

These repos are listed in the enforcement report but do **not** cause CI failure.

To make a not-yet-enforceable repo enforceable, add a
`.spectrum-governance.json` file under `governance/examples/manifests/` following
the schema in `governance/schemas/spectrum-governance.schema.json`.

## Where Governed Repos Declare Contract Usage

Each governed repo is expected to have a `.spectrum-governance.json` manifest
(stored in `governance/examples/manifests/` in this repo) that contains a
`contracts` section mapping each `artifact_type` to its pinned version:

```json
{
  "system_id": "my-engine",
  "repo_name": "my-engine",
  "repo_type": "operational_engine",
  "governance_repo": "spectrum-systems",
  "governance_version": "1.0.0",
  "contracts": {
    "reviewer_comment_set": "1.0.0",
    "comment_resolution_matrix": "1.0.0"
  }
}
```

Each `artifact_type` key must exist in `contracts/standards-manifest.json` and the
version must exactly match the `schema_version` from that manifest.

## Output Artifacts

| Artifact | Path | Format |
|---|---|---|
| Contract dependency graph | `governance/reports/contract-dependency-graph.json` | JSON |
| Human-readable enforcement report | `docs/governance-reports/contract-enforcement-report.md` | Markdown |

### Contract Dependency Graph

The graph is a machine-readable JSON file suitable for diffing in git.  It
contains:

- `repos`: One entry per ecosystem repo with `repo_name`, `repo_type`,
  `system_id`, `contracts_consumed` (with per-pin drift flags),
  `validation_status`, and any `failures`/`warnings`.
- `contract_index`: Reverse lookup from `artifact_type` → list of consumers
  with canonical version and stability status.

### Enforcement Report

The markdown report summarises:
- Repos inspected and their overall status (pass/fail/warning/not-yet-enforceable)
- All enforcement failures in the canonical CI output format
- All consumer-consistency warnings
- Remediation actions for each finding

## CI Integration

The enforcement runs as the `contract-enforcement` job in
`.github/workflows/cross-repo-compliance.yml`.

Trigger conditions (same as other compliance jobs):
- Push to `main` touching `governance/**`, `contracts/**`, `schemas/**`, or `ecosystem/**`
- Weekly on Mondays at 09:00 UTC
- Manual `workflow_dispatch`

The job:
1. Runs `python scripts/run_contract_enforcement.py`
2. Prints a structured enforcement summary to the log
3. Uploads `contract-dependency-graph.json` and `contract-enforcement-report.md` as CI artifacts
4. **Fails the job** if any repos have `validation_status: fail`
5. Does **not** fail for warnings or not-yet-enforceable repos

## Policy Engine Integration

The policy engine (`governance/policies/run-policy-engine.py`) also includes
two new policies that complement the enforcement script:

| Policy | Severity | Description |
|---|---|---|
| `GOV-009` | error | Contract version drift — pinned version in a governance manifest differs from the canonical version. |
| `GOV-010` | warning | Intended consumer gap — a repo listed as `intended_consumer` in the standards manifest does not declare the contract in its governance manifest. |

These policies are evaluated by the `policy-engine` CI job and produce structured
reports in `artifacts/policy-engine-report.json`.

## Current Enforcement Findings

Run `python scripts/run_contract_enforcement.py` to see the current state.
The latest generated report lives at
`docs/governance-reports/contract-enforcement-report.md`.

As of the initial implementation, the ecosystem has:
- **0 enforcement failures**
- **2 consumer-consistency warnings** for `meeting_minutes_record` (intended
  consumers `meeting-minutes-engine` and `spectrum-program-advisor` have not yet
  added this contract to their governance manifests)
- **0 not-yet-enforceable repos**
