# Runbook: Eval Constraint Failures (Batch / Umbrella)

**System:** EVAL  
**Gates:** batch_constraint_check, umbrella_constraint_check  
**Failure artifact type:** structured_failure

---

## Quick Diagnosis (2 minutes)

```
FAILURE: EVAL/batch_constraint_check
WHY:  BATCH-001 has 14 slices, exceeds max=10

FAILURE: EVAL/umbrella_constraint_check
WHY:  UMBRELLA-002 has 7 batches, exceeds max=5
```

---

## Pattern 1: Batch over max slices

**Limit:** 10 slices per batch (default)

**Fix:**
1. Split the batch at the work-planning stage before execution
2. Each batch must stay at ≤10 slices
3. Schedule the split batches sequentially — each needs its own eval gate pass

---

## Pattern 2: Umbrella over max batches

**Limit:** 5 batches per umbrella (default)

**Fix:**
1. Split the umbrella into two separate umbrellas at the roadmap level
2. Each umbrella must stay at ≤5 batches
3. Promote each umbrella independently

---

## Pattern 3: constraint_violated flag

```
FAILURE: EVAL/batch_constraint_check
WHY:  BATCH-001 constraint_violated=True
```

**Cause:** An explicit constraint violation was set on the batch, not just a count overflow.

**Fix:**
1. Find the event or gate that set `constraint_violated=True`
2. Investigate why — this flag means a logical constraint was broken, not just size
3. Fix the underlying violation before re-running

---

## Prevention

- Plan work in slices of ≤10 before creating batches
- Plan roadmaps with ≤5 batches per umbrella
- Do NOT raise limits without a governance review

---

## See Also

- `docs/runbooks/eval_gate_failures.md` — combined eval gate failures
- `spectrum_systems/eval_system/eval_system.py` — batch_constraint_check, umbrella_constraint_check
