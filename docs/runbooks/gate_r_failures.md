# Runbook: GATE-R Failures (Release/Budget)

**Gate:** GATE-R  
**Category:** SAFETY  
**Checks:** Release semantics (canary) + budget compliance + security approval

---

## What GATE-R validates

1. A canary record exists before promotion (`require_canary_before_promotion`)
2. Budget compliance: cost and token usage within limits
3. Security approval present for the artifact's risk level

---

## Pattern 1: Missing canary record

```
GATE-R failed: canary_gate_ok=False
WHY: No canary record found for artifact ART-001 before promotion
```

**Cause:** Artifact was promoted without a canary test record.

**Fix:**
1. Run the canary deployment for this artifact
2. `ReleaseSemanticsGate.emit_canary_record(artifact_id, deployment_pct)` must be called first
3. Only after the canary record exists can promotion proceed

---

## Pattern 2: Budget exceeded

```
GATE-R failed: budget_ok=False
WHY: cost=120, budget=100
```

**Cause:** Execution exceeded its declared budget.

**Fix:**
1. Review the execution cost vs. the declared budget
2. Either reduce the execution scope, or request a budget increase through governance
3. Do NOT increase budget unilaterally — requires a governance review

---

## Pattern 3: Security approval missing

```
GATE-R failed: sec_ok=False
WHY: Risk level=HIGH requires manual security approval
```

**Cause:** `HIGH` risk artifacts require manual security review before promotion.

**Fix:**
1. Submit the artifact for a security review
2. After review, the security approver sets `security_approved=True`
3. `LOW` risk artifacts are auto-approved; `MEDIUM`/`HIGH` require manual review

---

## See Also

- `spectrum_systems/modules/release/release_semantics.py`
- `spectrum_systems/modules/budget/cap_enforcer.py`
- `spectrum_systems/modules/security/sec_guardrail.py`
