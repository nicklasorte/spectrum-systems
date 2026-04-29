# TST-20 — Post-Cutover Audit

**Produced:** 2026-04-29  
**Branch:** claude/ci-test-consolidation-VV6y4  
**Note:** This document describes the target state. The cutover (TST-19) updates `pr-pytest.yml` to invoke `run_pr_gate.py`. Actual post-cutover audit will be updated after first successful PR through the canonical gate pipeline.

---

## Failure Clarity

**Before:** A developer seeing `PR / pytest` fail needed to read `contract_preflight_report.md`, `contract_preflight_diagnosis_bundle.md`, and inline workflow Python output to understand the failure.

**After:** `outputs/pr_gate/pr_gate_result.json` provides:
- `blocking_gate`: which gate failed
- `failure_summary.root_cause`: exact root cause string
- `failure_summary.blocking_reason`: human-readable reason
- `failure_summary.next_action`: what to do
- `failure_summary.affected_files`: which files are involved
- `failure_summary.failed_command`: exact command that failed
- `failure_summary.artifact_refs`: where to look for more details

A developer sees one clear reason per failure without reading five JSON files.

---

## Gate Coverage (Target State)

| Invariant | Gate | Covered? |
|---|---|---|
| Schema validity | Contract Gate | ✓ |
| Artifact boundary | Contract Gate | ✓ |
| Module architecture | Contract Gate | ✓ |
| Authority shape | Contract Gate | ✓ |
| Test selection non-empty | Test Selection Gate | ✓ |
| Selection provenance | Test Selection Gate | ✓ |
| Fallback smoke suite | Test Selection Gate | ✓ |
| Test execution | Runtime Test Gate | ✓ |
| Strategy compliance | Governance Gate | ✓ |
| Registry drift | Governance Gate | ✓ |
| Eval CI | Certification Gate | ✓ |
| SEL replay | Certification Gate | ✓ |
| Fail-closed behavior | Certification Gate | ✓ |

---

## Runtime

Target PR gate total: ≤ 4 minutes (fast path, no cert gate). See `docs/governance/ci_runtime_budget.md` for full budget table.

---

## Required Check Alignment

After cutover:
- `PR / pytest` remains the required check (no branch protection changes required)
- The `pytest` job in `pr-pytest.yml` calls `run_pr_gate.py`
- Other workflow jobs remain non-required (informational/redundancy)

---

## Developer Experience

Before: "Something failed in PR/pytest. Read contract_preflight_report.md and the inline Python output."

After: "PR blocked at contract_gate: `strategy_gate_decision=WARN is not pass-equivalent for pull_request`. Next action: Resolve WARN conditions before merging. See outputs/contract_preflight/contract_preflight_result_artifact.json."
