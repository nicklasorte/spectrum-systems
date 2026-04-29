# Required Check Cleanup Instructions

**Produced:** 2026-04-29 (TST-22)  
**Context:** These instructions must be applied manually in GitHub's repository settings because branch protection rules cannot be changed from repo code.

---

## Current State

- **Single required check:** `PR / pytest` (the `pytest` job in `pr-pytest.yml`)
- **Declared in:** `docs/governance/required_pr_checks.json`

---

## Target State (Post-Cutover)

The `PR / pytest` check name should remain required. The underlying implementation will change (from inline logic to `run_pr_gate.py`) without requiring a branch protection change.

No branch protection changes are required for TST-19 cutover.

---

## Manual Cleanup Steps (If Branch Protection Rules Need Updating)

If the required check name changes after cutover or if additional gates need to be required:

### Step 1: Navigate to branch protection settings

1. Go to `https://github.com/nicklasorte/spectrum-systems/settings/branches`
2. Click "Edit" on the main branch protection rule

### Step 2: Update required status checks

Under "Require status checks to pass before merging":
- **Remove:** Any stale check names that no longer exist
- **Add:** New check names from the canonical gate workflow

### Step 3: Current checks to verify

| Check Name | Should Be Required? |
|---|---|
| `PR / pytest` | **Yes** — keep required |
| `artifact-boundary / enforce-artifact-boundary` | Optional (informational) |
| `artifact-boundary / validate-module-architecture` | Optional (informational) |
| `artifact-boundary / system-registry-guard` | Optional (informational) |
| `artifact-boundary / governed-contract-preflight` | Optional (redundant with PR/pytest) |
| `artifact-boundary / run-pytest` | **NO** — non-authoritative, should not be required |

### Step 4: Post-cutover (if `pr-pytest.yml` renamed or jobs renamed)

If the `pytest` job in `pr-pytest.yml` is renamed (e.g., to `pr-gate`) the required check name changes from `PR / pytest` to `PR / pr-gate`. Update `docs/governance/required_pr_checks.json` and the branch protection rule together.

---

## Governance Note

`docs/governance/required_pr_checks.json` is the source of truth for declared required checks. Any change to branch protection rules must be reflected in this file within the same PR.
