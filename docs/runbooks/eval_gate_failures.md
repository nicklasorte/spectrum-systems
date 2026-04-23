# Runbook: Eval Gate Failures

**System:** EVAL  
**Gate:** eval_gate  
**Failure artifact type:** gate_decision (decision=block)

---

## Quick Diagnosis (2 minutes)

Find the failing check in `blocking_checks`:

```
FAILURE: EVAL/eval_gate
blocking_checks: ["provenance_complete"]  ← provenance failure
blocking_checks: ["batch_constraint"]     ← batch overflow
blocking_checks: ["eval_pass_rate"]       ← low pass rate
```

---

## Pattern 1: provenance_complete failed

**Cause:** Artifact is missing `trace_id` or was flagged `execution_without_provenance`.

**Fix:**
1. Check if artifact has `trace_id` — if not, it was created outside the runtime
2. Check for `execution_without_provenance=True` flag — find who set it
3. All execution must flow through PQX; re-run through the governed path

---

## Pattern 2: batch_constraint failed

```
WHY:  batch_id=BATCH-001 has 12 slices, exceeds max=10
```

**Cause:** Too many slices in one batch.

**Fix:**
1. Split the batch into two: ≤10 slices each
2. Promote each batch independently through the eval gate
3. Adjust the upstream work planner to stay within batch limits

---

## Pattern 3: eval_pass_rate failed

```
WHY:  pass_rate=0.89 < threshold=0.95 — blocked
```

**Cause:** More than 5% of eval cases are failing for this execution.

**Fix:**
1. Look at the eval result artifact for this trace — find which cases failed
2. Common causes: prompt regression, schema change, stale fixture
3. Fix the failures before re-running the eval gate
4. Do NOT lower the threshold — it is a safety gate

---

## See Also

- `docs/runbooks/eval_provenance_failures.md` — provenance-specific failures
- `docs/runbooks/eval_constraint_failures.md` — batch/umbrella constraint failures
- `spectrum_systems/eval_system/eval_system.py` — EVALSystem implementation
