# Runbook: Admission Gate Failures

**System:** EXEC / AEX  
**Gate:** admission_gate  
**Failure artifact type:** gate_decision (decision=block)

---

## Quick Diagnosis (2 minutes)

The admission gate runs four checks in sequence. Find which check failed:

```
FAILURE: EXEC/admission_gate
blocking_checks: ["input_schema_valid"]   ← schema failure
blocking_checks: ["context_integrity"]    ← context failure
blocking_checks: ["security_admission"]   ← security failure
blocking_checks: ["resource_availability"] ← resource failure
```

---

## Pattern 1: input_schema_valid failed

**Cause:** Artifact does not match the declared schema for its `artifact_type`.

**Fix:**
1. Get the schema: `schemas/artifacts/<artifact_type>.schema.json`
2. Compare artifact fields to schema — find the missing or mistyped field
3. Fix the artifact producer, not the schema

---

## Pattern 2: context_integrity failed

**Cause:** Context bundle is incomplete or stale.

**Fix:**
1. Check `context_bundle.schema.json` required fields
2. If context is stale: regenerate it from the source authority layer
3. If context is missing: trace back to why it was not attached at creation

---

## Pattern 3: security_admission failed

**Cause:** Artifact has a security flag set, or is missing a required security approval.

**Fix:**
1. Look for `security_flag` or `security_blocked=True` in the artifact
2. Check `docs/runbooks/gate_r_failures.md` for the security approval flow
3. Low-risk artifacts can get approval via `get_security_approval()` automatically

---

## Pattern 4: resource_availability failed

**Cause:** System resources (memory, execution budget) are insufficient.

**Fix:**
1. Check system resource metrics in the monitoring dashboard
2. If resources are under load: wait and retry
3. If persistent: reduce execution scope_items in the request

---

## See Also

- `docs/runbooks/exec_admission_failures.md` — EXEC-specific admission failures
- `spectrum_systems/execution/admission_gate.py` — AdmissionGate implementation
