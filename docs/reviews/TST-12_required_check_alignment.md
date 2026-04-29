# TST-12 — Required Check Alignment Audit

**Produced:** 2026-04-29  
**Branch:** claude/ci-test-consolidation-VV6y4

---

## Current Required Checks

Per `docs/governance/required_pr_checks.json`:

```json
{
  "policy_version": "1.0.0",
  "workflow": "PR",
  "authoritative_job_id": "pytest",
  "authoritative_display_name": "pytest",
  "required_status_check_name": "PR / pytest"
}
```

**Only one required check is declared:** `PR / pytest` (the `pytest` job in `pr-pytest.yml`).

---

## Canonical Target Checks

After consolidation, the target required checks are:

| Check Name | Workflow | Gate | Status |
|---|---|---|---|
| `PR / pytest` | `pr-pytest.yml` | Contract Gate + Runtime Test Gate | **KEEP** (canonical) |
| `artifact-boundary / enforce-artifact-boundary` | `artifact-boundary.yml` | Contract Gate | Overlaps with PR/pytest |
| `artifact-boundary / validate-module-architecture` | `artifact-boundary.yml` | Contract Gate | Overlaps with PR/pytest |
| `artifact-boundary / system-registry-guard` | `artifact-boundary.yml` | Contract Gate | Overlaps with PR/pytest |
| `artifact-boundary / governed-contract-preflight` | `artifact-boundary.yml` | Contract Gate | Overlaps with PR/pytest |

---

## Stale / Duplicate Checks

| Check Name | Status | Reason |
|---|---|---|
| `artifact-boundary / run-pytest` | **STALE — non-authoritative** | Explicitly marked "Non-authoritative redundancy signal only" in the workflow |
| `artifact-boundary / governed-contract-preflight` | **DUPLICATE** | Runs the same `run_contract_preflight.py` as `PR / pytest`. Produces a different artifact but enforces the same policy. |

---

## Missing Checks

| Check | Should Be Required | Action |
|---|---|---|
| Governance gate (for governance path PRs) | Yes — when `docs/governance/` is touched | Add `PR / governance-gate` or ensure it's enforced via `strategy-compliance` |
| Certification gate (for cert path PRs) | Yes — when cert-relevant paths are touched | Currently embedded in `lifecycle-enforcement.yml` but not a required PR check |

---

## Analysis

The current required check model is **minimal but functional**:
- `PR / pytest` is the single authoritative gate
- All other workflow jobs are informational or redundant
- This is intentional per `docs/governance/required_pr_checks.json`

**After canonical gate consolidation**, the target model should be:
- `PR / contract-gate` or retain `PR / pytest` as the consolidated gate
- The consolidation does not require changing GitHub branch protection rules — the new canonical gate can be invoked via the existing `pr-pytest.yml` workflow, renamed or updated to call `run_pr_gate.py`

---

## Recommendations

1. **Retain `PR / pytest`** as the required check name during migration to avoid branch protection changes.
2. **Update `pr-pytest.yml`** to call `run_pr_gate.py` instead of the inline logic — this preserves the check name while consolidating to canonical gates.
3. **Mark `artifact-boundary / run-pytest`** as non-required (it already is) and add a comment in the workflow.
4. **Add `required_check_cleanup_instructions.md`** with exact instructions for updating GitHub branch protection once parity is proven (TST-22).
