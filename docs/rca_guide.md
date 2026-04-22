# Root Cause Analysis (RCA) Guide

**Target:** -20% RCA time from baseline
**Method:** Structured failure messages + 20 example cases + decision tree

---

## How to Use This Guide

Each failure message in Spectrum Systems now uses structured format:

```
FAILURE: SYSTEM/gate_id

  WHAT: Artifact failed <check_name> check
  WHY:  Observed <value>, expected <value>
  NEXT: See runbook: docs/runbooks/<guide>.md
  CONTEXT: trace_id=..., artifact_id=...
```

**Time to first diagnosis: < 2 minutes** using the lookup tables below.

---

## Failure Pattern Index

### Pattern 1: Missing required field

**Symptom:**
```
FAILURE: EXEC/exec_check
WHY:  Observed missing required fields ['trace_id'], expected all present
```

**Root Cause:** Artifact was created without setting `trace_id`. Usually means
the artifact was constructed outside the governed runtime (bypassing AEX).

**Fix:**
1. Find where the artifact was created (search for `artifact_type` value)
2. Ensure it flows through AEX → EXEC admission
3. All artifacts must have `artifact_type` and `trace_id`

---

### Pattern 2: Lineage broken

**Symptom:**
```
FAILURE: EXEC/exec_check
WHY:  Observed lineage_complete=False, expected lineage_complete=True
```

**Root Cause:** One or more upstream artifacts in the lineage chain were not
produced or were produced outside the governed runtime.

**Fix:**
1. Run: `spectrum_systems/modules/lineage/lineage_verifier.py` on the trace
2. Find the first artifact in the chain with `upstream_artifacts=[]` that should not be empty
3. Re-run the missing upstream step
4. Do not manually set `lineage_complete=True` — it must be earned

---

### Pattern 3: Eval pass rate below threshold

**Symptom:**
```
FAILURE: EVAL/eval_gate
WHY:  pass_rate=0.823 < threshold=0.950 — blocked
```

**Root Cause:** More than 5% of evaluations are failing. Could be:
- Real quality regression in the execution output
- Stale eval fixtures (run GATE-C to detect)
- Threshold mismatch (rare — check if threshold was lowered)

**Fix:**
1. Identify failing eval cases: query eval_result artifacts for this trace
2. Cluster failures by check type
3. If systematic: fix the root issue in execution
4. If fixture stale: update fixtures through governed adoption
5. Do not lower the threshold — it's a hard governance boundary

---

### Pattern 4: Policy drift detected

**Symptom:**
```
FAILURE: GOVERN/policy_check
WHY:  Observed authorization_level=unauthorized, expected authorized
```

**Root Cause:** The artifact bypassed EXEC trust admission, or the authorization
was revoked after admission.

**Fix:**
1. Check if the artifact went through EXEC.exec_check (look for `admission_gate` event)
2. If it skipped EXEC: re-route through the full admission path
3. If authorization was revoked: check GOV policy for the artifact type

---

### Pattern 5: Lifecycle transition blocked

**Symptom:**
```
FAILURE: GOVERN/lifecycle_check
WHY:  cannot transition 'executing_slice_2' → 'promoted' (allowed: {'executing_slice_3'})
```

**Root Cause:** Attempting to skip execution slices. All three slices must complete.

**Fix:**
1. Check which slices have completed (event log: `execution_start`/`execution_end`)
2. Complete the missing slice(s)
3. Allow state to naturally progress to `certification_pending`

---

### Pattern 6: Batch constraint violation

**Symptom:**
```
FAILURE: EVAL/batch_constraint_check
WHY:  batch_id=BATCH-007 has 14 slices, exceeds max=10
```

**Root Cause:** Work was batched too aggressively. Max 10 slices per batch.

**Fix:**
1. Split the batch into multiple smaller batches (each ≤ 10 slices)
2. Re-submit through EXEC admission

---

### Pattern 7: Hard gate falsification failure

**Symptom:**
```
FAILURE: sequence_transition_policy/hard_gate_falsification_passes
WHY:  pqx_hard_gate_falsification_record has only 6/8 required checks passed
```

**Root Cause:** The PQX hard-gate falsification record is incomplete. This is a
correctness gate — execution must demonstrate all 8 falsification checks pass.

**Fix:**
1. Find the `pqx_hard_gate_falsification_record` artifact for this trace
2. Identify which of the 8 checks failed
3. Fix the underlying issue the check is detecting
4. Rerun the falsification harness

---

### Pattern 8: Promotion gate SLO failure

**Symptom:**
```
FAILURE: PromotionGate/slo_compliant
WHY:  budget_used=1250 exceeds budget_limit=1000 — SLO violation
```

**Root Cause:** Execution consumed more resources than the SLO budget allows.

**Fix:**
1. Check resource usage in execution (event log: `execution_end` data)
2. Optimize the most expensive operation, or request a budget increase through CAP
3. Do not override the SLO limit inline

---

### Pattern 9: Security admission blocked

**Symptom:**
```
FAILURE: EXEC/exec_check
WHY:  artifact flagged trust_blocked
```

**Root Cause:** The artifact has `trust_blocked=True`, usually set by a security
guardrail (SEC system).

**Fix:**
1. Check SEC guardrail log for why the artifact was blocked
2. Address the security finding
3. Resubmit — do not clear `trust_blocked` manually

---

### Pattern 10: Replay non-determinism

**Symptom:**
```
FAILURE: PromotionGate/replay_deterministic
WHY:  replay_deterministic=false — non-deterministic output blocked
```

**Root Cause:** Two replay runs of the same execution produced different outputs.
This means the execution contains non-determinism (time-dependent, random, external state).

**Fix:**
1. Find the execution function that uses non-deterministic inputs
2. Seed random generators, freeze time mocks, or stub external calls
3. Rerun replay harness until both runs match

---

### Pattern 11: CDE closure blocked (frozen)

**Symptom:**
```
FAILURE: CDE/closure_decision
WHY:  action=freeze — hold pending human review
```

**Root Cause:** CDE has frozen the artifact pending human review. Not an error.

**Fix:**
1. Find the freeze reason in the `control_decision` artifact
2. Address the condition that triggered the freeze
3. Re-submit through CDE once the condition clears

---

### Pattern 12: Roadmap misalignment

**Symptom:**
```
FAILURE: EXEC/roadmap_alignment_check
WHY:  roadmap_ref='FEAT-99' not in active roadmap items
```

**Root Cause:** The work being executed is not on the active roadmap. Prevents
unplanned work from reaching production.

**Fix:**
1. Verify `FEAT-99` is a real work item
2. Add it to the active roadmap through a governed adoption PR
3. Do not skip the roadmap check

---

### Pattern 13: Gate-F (Foundation) failure

**Symptom:**
```
GATE-F failed: RegistryDriftValidator import error
```

**Root Cause:** The registry drift validator cannot be imported. Usually a
missing dependency or import path issue.

**Fix:**
1. Check that `spectrum_systems/governance/registry_drift_validator.py` exists
2. Run `python -m pytest tests/test_3ls_phase1_foundation.py -q`
3. Fix any import errors shown

---

### Pattern 14: Gate-O (Observability) failure

**Symptom:**
```
GATE-O failed: obs_emitter missing required field 'trace_id'
```

**Root Cause:** OBS emitter was called without a trace_id.

**Fix:**
1. Find the OBS emit call in the execution path
2. Ensure trace_id is threaded through from AEX intake
3. All OBS records require trace_id for replay determinism

---

### Pattern 15: Event log immutability violation

**Symptom:**
```
TypeError: ExecutionEvent is immutable — no modifications allowed after creation
```

**Root Cause:** Code attempted to modify an event after it was logged.

**Fix:**
1. Find the code that calls `event["field"] = value` after `log_event()`
2. Events are write-once — create a new event instead
3. This is a hard invariant: the event log is append-only

---

### Pattern 16: GOVERN lifecycle — unknown current_state

**Symptom:**
```
FAILURE: GOVERN/lifecycle_check
WHY:  cannot transition '' → 'executing_slice_1' (allowed: set())
```

**Root Cause:** Artifact has no `lifecycle_state` field (empty string).

**Fix:**
1. Artifacts must enter with `lifecycle_state='admitted'` from AEX
2. Check the AEX admission step set the initial lifecycle state

---

### Pattern 17: Checkpoint state invalid

**Symptom:**
```
FAILURE: EVAL/checkpoint_resume_check
WHY:  state='unknown' not in valid states {'ready', 'resumable', 'complete'}
```

**Root Cause:** A checkpoint artifact has an unexpected state value.

**Fix:**
1. Find where the checkpoint artifact was created
2. Valid states: `ready`, `resumable`, `complete`
3. Update the checkpoint-creation logic to use a valid state

---

### Pattern 18: GATE-J (Judgment) evidence insufficient

**Symptom:**
```
GATE-J failed: judgment evidence requires at least 2 evidence_artifacts
```

**Root Cause:** The judgment record does not have enough supporting evidence.

**Fix:**
1. Find the judgment record for this trace
2. Add at least 2 evidence artifact references
3. Evidence must be real artifacts from earlier in the pipeline

---

### Pattern 19: System not in justification registry

**Symptom:**
```
System proposal rejected: justification registry is locked.
```

**Root Cause:** Code is attempting to add a new system, but the registry is
locked. Requires governed adoption.

**Fix:**
1. Open a PR that adds the system to `SYSTEM_JUSTIFICATIONS` in `system_justification.py`
2. The system must have `prevents` and `improves` entries
3. PR must go through full governance review

---

### Pattern 20: Promotion without done_certification_record

**Symptom:**
```
BLOCK: terminal_state != ready_for_merge — promotion denied
```

**Root Cause:** Attempting to promote to main without a passing
`done_certification_record`. This is a hard governance rule.

**Fix:**
1. Run all certification checks: `python -m pytest -q`
2. All tests must pass
3. All gates must be GREEN
4. Only then will `terminal_state == ready_for_merge`

---

## RCA Efficiency Tips

1. **Start with the event log** — `EventFilter.failure_view(events)` shows only failures
2. **Structured messages tell you the gate** — go directly to the right section above
3. **Most failures are in patterns 1-5** — check those first
4. **Never skip a gate** — every block exists for a reason
5. **Escalate contradictions** — do not resolve ambiguity by inference
