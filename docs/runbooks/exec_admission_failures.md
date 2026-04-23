# Runbook: EXEC Admission Gate Failures

**System:** EXEC  
**Gate:** exec_check  
**Failure artifact type:** structured_failure

---

## Quick Diagnosis (2 minutes)

1. Read `WHY` field in the failure message
2. Match to pattern below
3. Follow the fix steps

---

## Pattern 1: Missing required field

```
FAILURE: EXEC/exec_check
WHY:  Observed missing required fields ['trace_id'], expected all present
```

**Cause:** Artifact was created outside AEX (no trace_id assigned).

**Fix:**
1. Find where the artifact is constructed — search for its `artifact_type`
2. Ensure it flows through AEX before reaching EXEC
3. Every artifact needs `artifact_type` and `trace_id` at construction

---

## Pattern 2: Lineage incomplete

```
FAILURE: EXEC/exec_check
WHY:  Observed lineage_complete=False, expected True
```

**Cause:** Upstream artifacts in the lineage chain are missing.

**Fix:**
1. Run `lineage_verifier.py` on the trace_id
2. Find first artifact with empty `upstream_artifacts` that should not be empty
3. Re-run the missing upstream step — do NOT set `lineage_complete=True` manually

---

## Pattern 3: Trust blocked

```
FAILURE: EXEC/exec_check
WHY:  Observed trust_blocked=True, expected False
```

**Cause:** Artifact was explicitly flagged `trust_blocked` by a prior gate or policy check.

**Fix:**
1. Check the event log for the event that set `trust_blocked=True`
2. Identify which policy or gate set the flag
3. Fix the underlying issue and re-admit the artifact through EXEC

---

## Pattern 4: Scope over budget

```
FAILURE: EXEC/trust_scope_check
WHY:  Observed scope_items=55, expected scope_items <= 50
```

**Cause:** Execution request exceeds the complexity budget.

**Fix:**
1. Split the work into smaller slices (≤50 scope items each)
2. Each slice goes through its own admission gate
3. Do NOT raise the budget without a governance review

---

## See Also

- `docs/runbooks/govern_policy_failures.md` — policy-level blocks
- `docs/rca_guide.md` — full failure pattern library
- `spectrum_systems/exec_system/exec_system.py` — EXECSystem implementation
