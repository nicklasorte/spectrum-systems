# Runbook: GATE-J Failures (Judgment/Policy)

**Gate:** GATE-J  
**Category:** SAFETY  
**Checks:** Evidence sufficiency + policy lifecycle validation

---

## What GATE-J validates

1. `validate_judgment_evidence` runs and evidence artifacts are present
2. `apply_policy` runs and policy status is valid (not expired)

---

## Pattern 1: Judgment evidence insufficient

```
GATE-J failed: validate_judgment_evidence returned False
```

**Cause:** Judgment artifact has fewer than the required minimum evidence artifacts.

**Fix:**
1. Check the judgment artifact for `evidence_artifacts` list
2. Minimum required: 2 evidence artifacts
3. Add the missing evidence (eval results, review records) before re-running GATE-J

---

## Pattern 2: Policy expired

```
GATE-J failed: policy status=expired, expires_at=<date>
```

**Cause:** The policy used for this judgment has expired.

**Fix:**
1. Find the policy in the policy registry
2. Issue a policy renewal via the governance review process
3. Do NOT use an expired policy — update it before proceeding

---

## Pattern 3: Policy status invalid

**Cause:** Policy has a status other than `active` (e.g., `draft`, `deprecated`, `revoked`).

**Fix:**
1. Find the policy and determine why it is not `active`
2. If `draft`: complete the policy review and activate it
3. If `deprecated` or `revoked`: find the replacement policy

---

## See Also

- `spectrum_systems/modules/governance/judgment.py`
- `spectrum_systems/modules/governance/policy_lifecycle.py`
