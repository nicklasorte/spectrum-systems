# PYX-03 — PR check surface diagnosis

## Inspection summary
Inspected surfaces:
- `.github/workflows/*.yml` (all workflows)
- Reusable workflow usage (`workflow_call` and workflow `uses`) — none found
- Composite actions under `.github/actions` — none present
- Current required-check policy declaration: `docs/governance/required_pr_checks.json`
- Required-check audit logic/tests:
  - `scripts/run_required_check_alignment_audit.py`
  - `spectrum_systems/modules/runtime/required_check_alignment_audit.py`
  - `tests/test_required_check_alignment_audit.py`
  - `tests/test_artifact_boundary_workflow_pytest_enforcement.py`

## What check names GitHub is likely surfacing
The authoritative pytest gate currently lives in `.github/workflows/artifact-boundary.yml` as job id `pytest-pr` with job display name `PR / pytest`.

For GitHub Actions PR checks, the surfaced check-run context for a named job in a named workflow is workflow-prefixed. That means the PR-visible context is expected to be:

- `artifact-boundary / PR / pytest`

not plain `PR / pytest`.

## Why PYX-02 did not produce a visible `PR / pytest` check in merge UI
PYX-02 renamed the **job** to `PR / pytest` but left it inside workflow `artifact-boundary`, so the surfaced check context remained workflow-prefixed (`artifact-boundary / PR / pytest`).

At the same time, this repository still has multiple generic PR workflows (for example `lifecycle-enforcement`) that produce generic-prefixed contexts, so operators continue to see generic workflow surfaces and do not get a standalone pytest-explicit required check context.

## Classification of the defect
This is primarily a **workflow-name-level check-surface issue**, not a trust-path implementation issue.

- Not a reusable-workflow issue (none are used).
- Not a missing pytest execution authority issue (authoritative governed preflight logic is present and strict).
- It is a surfaced check-context naming issue: the authority path is nested under a generic workflow umbrella.

## Required fix
To guarantee an explicit and stable PR-visible pytest check context, move the existing authoritative governed preflight/pytest job into a dedicated PR workflow named `PR` with job name `pytest`.

Expected surfaced context after fix:
- `PR / pytest`

This keeps the same governed preflight artifact/trust enforcement while making the surfaced required check explicit.

## Policy/audit implication
Because required check matching should use the actual surfaced context name, update policy and audit expectations to `PR / pytest` derived from:
- workflow name: `PR`
- authoritative job id: `pytest`
- authoritative job display name: `pytest`
- required status check context: `PR / pytest`

No trust weakening is required; this is a check-surface alignment fix.
