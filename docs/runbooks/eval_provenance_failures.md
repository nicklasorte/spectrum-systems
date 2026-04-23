# Runbook: Eval Provenance Failures

**System:** EVAL  
**Gate:** provenance_check / validate_provenance  
**Failure artifact type:** structured_failure

---

## Quick Diagnosis (2 minutes)

```
FAILURE: EVAL/provenance_check
WHY:  Observed trace_id=None, expected trace_id present
```

or

```
FAILURE: EVAL/provenance_check
WHY:  Observed execution_without_provenance=True, expected False
```

---

## Pattern 1: Missing trace_id

**Cause:** Artifact was created without going through the governed admission path.

**Fix:**
1. Trace back to where the artifact was constructed
2. Ensure the artifact flows through AEX (which sets trace_id)
3. Never construct `execution_*` artifacts manually — they must come from PQX

---

## Pattern 2: execution_without_provenance flag

**Cause:** PQX or a downstream system detected execution occurred without provenance tracking.

**Fix:**
1. Check the event log for events before this failure — find where provenance was lost
2. Identify the execution path that bypassed provenance tracking
3. Close the bypass: all execution paths must log through ExecutionEventLog
4. Re-run the execution through the governed path

---

## Pattern 3: Incomplete provenance chain

**Cause:** `upstream_artifacts` list is empty when it should reference prior execution.

**Fix:**
1. Run `lineage_verifier.verify_lineage_completeness()` on the artifact
2. Find the gap in the upstream chain
3. Re-run the missing upstream step to restore the provenance link

---

## Prevention

- Always create artifacts through PQX, not directly
- All working-paper artifacts are created by `EVALSystem.generate_working_paper()`
- Never set `provenance_complete=True` manually

---

## See Also

- `docs/runbooks/eval_gate_failures.md` — combined eval gate failures
- `spectrum_systems/eval_system/eval_system.py` — EVALSystem.validate_provenance
