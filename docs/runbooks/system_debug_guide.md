# System Debug Guide: Simplified 3LS Architecture

**Version:** Post-consolidation (Phase 2 complete)
**Systems:** GOVERN, EXEC, EVAL (consolidated from TLC+GOV, TPA+PRG, WPG+CHK)
**Owner:** Platform Engineering
**Updated:** 2026-04-22

---

## Quick Diagnosis (2 minutes)

When something fails:

1. **Find the failure artifact** — look in event log for `event_type=failure` or a blocked gate decision
2. **Identify the system** — which of GOVERN / EXEC / EVAL / CDE / PQX / SEL?
3. **Find the gate** — `gate_id` in the gate_decision artifact
4. **Read the blocking check** — `blocking_checks` list + `reasons` dict
5. **Go to the section below** for that gate

---

## System Map (Post-Consolidation)

```
Input
  ↓
EXEC (admission, trust, roadmap alignment)
  ↓
GOVERN (policy check, lifecycle routing)
  ↓
PQX (execution — do not touch directly)
  ↓
EVAL (working paper, constraint checks)
  ↓
CDE (closure decision — sole authority)
  ↓
SEL (enforcement — fail-closed)
  ↓
Promotion
```

---

## GOVERN Gate Failures

### policy_check BLOCK

```
FAILURE: GOVERN/policy_check
WHY:  authorization_level=unauthorized
```

**Steps:**
1. Check the artifact's `authorization_level` field
2. Verify the upstream trust envelope was applied (EXEC.exec_check)
3. If artifact is legitimately authorized: check policy_ref matches active policy
4. If policy_ref missing: artifact must go through EXEC admission first

**Runbook:** `docs/runbooks/govern_policy_failures.md`

### lifecycle_check BLOCK (invalid transition)

```
FAILURE: GOVERN/lifecycle_check
WHY:  cannot transition 'admitted' → 'promoted' (allowed: {'executing_slice_1'})
```

**Steps:**
1. Check current `lifecycle_state` in the artifact
2. Verify the previous state transition completed (event log: `lifecycle_transition`)
3. All 3 execution slices must complete before `review_pending`
4. See `sequence_transition_policy.py` for the full allowed-transition map

---

## EXEC Gate Failures

### exec_check BLOCK (missing fields)

```
FAILURE: EXEC/exec_check
WHY:  missing required fields ['trace_id']
```

**Steps:**
1. The artifact is missing `artifact_type` or `trace_id`
2. Check the input source — was the artifact constructed correctly?
3. Verify the AEX admission step ran before EXEC

### exec_check BLOCK (lineage)

```
FAILURE: EXEC/exec_check
WHY:  lineage_complete=false
```

**Steps:**
1. Check `lineage_complete` field on the artifact
2. Run lineage verifier: `spectrum_systems/modules/lineage/lineage_verifier.py`
3. Identify which upstream artifact is missing from the lineage chain
4. Rerun the missing upstream step before re-submitting

### roadmap_alignment_check BLOCK

```
FAILURE: EXEC/roadmap_alignment_check
WHY:  roadmap_ref='FEAT-99' not in active roadmap items
```

**Steps:**
1. Verify `roadmap_ref` in the artifact matches an active roadmap entry
2. Check `config/roadmap_expansion_policy.json` for active items
3. If work item is valid but not in roadmap: open governed adoption PR first

---

## EVAL Gate Failures

### batch_constraint BLOCK

```
FAILURE: EVAL/batch_constraint_check
WHY:  batch_id=BATCH-001 has 12 slices, exceeds max=10
```

**Steps:**
1. Split the batch — max 10 slices per batch
2. Create two batches with ≤10 slices each
3. Re-submit through EXEC admission

### provenance BLOCK

```
FAILURE: EVAL/validate_provenance
WHY:  artifact EXEC-001 missing trace_id
```

**Steps:**
1. Every artifact requires `trace_id` for provenance
2. Check if the artifact was created outside the governed runtime
3. If so: re-create through the governed path (AEX → EXEC → GOVERN → PQX → EVAL)

### eval_gate BLOCK (pass rate)

```
FAILURE: EVAL/eval_gate
WHY:  pass_rate=0.872 < threshold=0.950 — blocked
```

**Steps:**
1. Look at the failing evaluations: check eval_result artifacts
2. Identify the failure pattern (same check failing multiple times?)
3. Fix the underlying issues and rerun evals
4. Do NOT lower the threshold — it exists for a reason

---

## CDE (Closure Decision) Failures

CDE is the sole decision authority. If CDE blocks:

1. Find the `control_decision` artifact: `action` field
2. Valid actions: `allow`, `warn`, `freeze`, `block`
3. `block`: hard stop — requires FRE diagnosis before retry
4. `freeze`: temporary hold — check freeze conditions, resolve, then unfreeze
5. Never bypass CDE — it is the only path to promotion

---

## SEL (Enforcement) Failures

SEL is fail-closed. If SEL blocks:

1. Find the SEL enforcement record
2. SEL only fires when a prior gate has already failed
3. Resolve the upstream gate failure first
4. SEL will clear automatically once the gate passes

---

## Common RCA Patterns

| Symptom | First Check | Root Cause |
|---------|-------------|------------|
| `lineage_complete=false` | EXEC exec_check | Missing upstream artifact |
| `authorization_level=unauthorized` | GOVERN policy_check | Artifact bypassed EXEC |
| `pass_rate < 0.95` | EVAL eval_gate | Evaluation failures in the run |
| `lifecycle invalid transition` | GOVERN lifecycle_check | Skipped an execution slice |
| `batch has N slices, exceeds max` | EVAL batch_constraint | Batch too large — split it |
| `roadmap_ref not in active items` | EXEC roadmap_alignment | Work item not on roadmap |

---

## How to Read the Event Log

```python
from spectrum_systems.observability.execution_event_log import ExecutionEventLog
from spectrum_systems.observability.event_filter import EventFilter

log = ExecutionEventLog()

# Debug view (all events for a trace)
all_events = log.get_execution_timeline("TRC-ABCD1234")

# Operator view (importance >= 3)
relevant = EventFilter.operator_view(all_events)

# Failure-only view (for RCA)
failures = EventFilter.failure_view(all_events)
```

---

## Escalation Path

1. Check this guide first
2. Check system-specific runbook (see FAILURE message NEXT field)
3. Check `docs/architecture/system_registry.md` for ownership
4. Open a governed issue in `/issues/` with the structured failure artifact
