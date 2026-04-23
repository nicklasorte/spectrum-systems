# Runbook: GOVERN Policy Check Failures

**System:** GOVERN  
**Gate:** policy_check  
**Failure artifact type:** structured_failure

---

## Quick Diagnosis (2 minutes)

```
FAILURE: GOVERN/policy_check
WHY:  artifact_type missing — cannot determine policy scope

FAILURE: GOVERN/policy_check
WHY:  artifact explicitly policy_blocked

FAILURE: GOVERN/policy_check
WHY:  authorization_level=unauthorized
```

---

## Pattern 1: artifact_type missing

**Cause:** Artifact was created without an `artifact_type` field.

**Fix:**
1. Find the artifact constructor — every artifact must declare its type
2. Add `artifact_type` matching a registered schema
3. Re-submit through EXEC → GOVERN

---

## Pattern 2: policy_blocked flag

**Cause:** A prior gate or policy rule explicitly set `policy_blocked=True` on the artifact.

**Fix:**
1. Search the event log for the event that set `policy_blocked=True`
2. Find the policy rule that triggered it
3. If the flag was set in error: fix the upstream gate logic
4. If the flag is correct: fix the artifact content to comply with policy

---

## Pattern 3: authorization_level=unauthorized

**Cause:** Artifact claims `authorization_level=unauthorized` — it has no authorization.

**Fix:**
1. Determine the correct authorization level for this artifact type
2. Ensure the artifact flows through the proper authorization path before GOVERN
3. Do NOT change `authorization_level` manually — it must come from the admission gate

---

## Checking Policy Drift

If the policy check passes but behavior seems wrong, use drift detection:

```python
from spectrum_systems.govern.govern import GOVERNSystem
govern = GOVERNSystem()
report = govern.detect_policy_drift(declared_policy, observed_behavior)
# report["has_drift"] == True means there's a mismatch
```

---

## See Also

- `docs/runbooks/govern_lifecycle_failures.md` — lifecycle routing failures
- `spectrum_systems/govern/govern.py` — GOVERNSystem.policy_check
