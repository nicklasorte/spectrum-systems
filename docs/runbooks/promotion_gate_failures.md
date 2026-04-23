# Runbook: Promotion Gate Failures

**System:** EXEC (PromotionGate)  
**Gate:** promotion_gate  
**Failure artifact type:** gate_decision (decision=block)

---

## Quick Diagnosis (2 minutes)

Find the blocking check:

```
FAILURE: EXEC/promotion_gate
blocking_checks: ["lineage_complete"]    ← lineage broken
blocking_checks: ["replay_integrity"]    ← replay hash mismatch
blocking_checks: ["prior_gates_passed"]  ← earlier gate not passed
blocking_checks: ["security_approved"]   ← missing security approval
blocking_checks: ["slo_compliant"]       ← SLO threshold missed
```

---

## Pattern 1: lineage_complete failed

**Cause:** Artifact lineage chain has a gap — an upstream artifact is missing.

**Fix:**
1. Run the lineage verifier on the artifact's trace_id
2. Find the first upstream artifact with an empty provenance chain
3. Re-run the missing step before re-attempting promotion

---

## Pattern 2: replay_integrity failed

**Cause:** Replay hash for the execution does not match the recorded hash (non-determinism detected).

**Fix:**
1. Check if any external dependency (random seed, timestamp, external API) was used in execution
2. Find the non-deterministic source and make it deterministic or remove it
3. Re-run the execution to get a consistent replay hash

---

## Pattern 3: prior_gates_passed failed

**Cause:** Promotion is attempting to skip gates — the admission or eval gate was not passed first.

**Fix:**
1. Run the full gate sequence: admission → eval → promotion
2. Do NOT attempt to promote an artifact that has not passed prior gates
3. Check the event log — find which gate was not logged as passed

---

## Pattern 4: security_approved failed

**Cause:** Artifact is missing the required security approval artifact.

**Fix:**
1. Check the artifact's risk classification (`LOW`, `MEDIUM`, `HIGH`)
2. For `LOW`: automatic approval via `get_security_approval()` — should not fail
3. For `MEDIUM`/`HIGH`: manual security review required before promotion

---

## Pattern 5: slo_compliant failed

```
WHY:  slo_compliance_rate=0.91 < 0.95
```

**Cause:** Execution missed its SLO targets.

**Fix:**
1. Find the SLO metrics for this trace in the monitoring dashboard
2. Identify which SLO dimension failed (latency, quality, error rate)
3. Fix the underlying issue before promoting

---

## See Also

- `docs/runbooks/gate_r_failures.md` — release/budget gate
- `spectrum_systems/promotion/promotion_gate.py` — PromotionGate implementation
