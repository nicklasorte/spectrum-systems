# 3LS Simplified Architecture Runbook

**Version:** 1.0  
**Phase:** 7 (Operator Training)  
**Date:** 2026-04-23  
**Owner:** Platform Operations

---

## System Overview

The 3LS simplification consolidates 10 original systems into 6 canonical authorities.

### Consolidated Architecture

The 3LS simplification consolidates 10 original systems into 3 new systems plus the two unchanged canonical authorities (GOV and AEX).

| System | Role | Absorbed From |
|--------|------|---------------|
| **EXEC** | Execution admissibility + program planning | TPA, PRG |
| **GOVERN** | Governance policy + lifecycle orchestration | GOV, TLC |
| **EVAL** | Evaluation provenance + constraint checking | WPG, CHK |
| **GOV** | Governance policy and fail-closed gate implementation | Unchanged |
| **AEX** | Admission exchange boundary | Unchanged |

### Execution Loop

```
Input → EXEC (admit) → GOVERN (policy + lifecycle)
      → AEX (execute) → EVAL (eval gates)
      → GOV (closure gate) → AEX (enforce)
      → promotion
```

---

## What Changed for Operators

### System Call Paths

**Before consolidation:**

```
TPA.tpa_check() + GOV.gov_policy() + TLC.tlc_route() (3 separate calls)
```

**After consolidation:**

```
EXEC.exec_check()     → covers TPA admissibility
GOVERN.policy_check() → covers GOV policy
GOVERN.route_artifact() → covers TLC routing
```

### Failure Messages

Failure messages now follow the **What / Why / How** format:

- **What failed:** System + gate name (e.g., `GOVERN policy_check`)
- **Why:** Root cause in plain language (e.g., `artifact missing metadata field: roadmap_ref`)
- **How to fix:** Runbook reference (e.g., `See: GOV_001 in RCA guide`)

Example:

```
EXEC exec_check BLOCK: missing required fields ['trace_id']
→ Add trace_id to artifact before calling exec_check
→ See: EXEC_001 in RCA guide
```

---

## Common Failure Scenarios

### Scenario 1: EXEC Admission Failure

**Symptom:** `exec_check BLOCK: missing required fields`

**Steps:**
1. Check artifact for missing `artifact_type` or `trace_id`
2. Check that `lineage_complete` is not explicitly `false`
3. Check that `trust_blocked` is not set
4. Add missing fields and retry
5. If still failing: check RCA guide case EXEC_001

**Code path:** `spectrum_systems/exec_system/exec_system.py:exec_check()`

---

### Scenario 2: GOVERN Policy Failure

**Symptom:** `policy_check BLOCK: artifact_type missing` or `authorization_level=unauthorized`

**Steps:**
1. Confirm artifact has `artifact_type` set
2. Confirm `policy_blocked` is not `True`
3. Confirm `authorization_level` is not `"unauthorized"`
4. Check policy registry for required artifact metadata
5. If still failing: check RCA guide case GOV_001

**Code path:** `spectrum_systems/govern/govern.py:policy_check()`

---

### Scenario 3: GOVERN Lifecycle Block

**Symptom:** `lifecycle_check BLOCK: cannot transition 'X' → 'Y'`

**Steps:**
1. Check artifact's current `lifecycle_state`
2. Confirm target state is a valid next state from the current state
3. Valid transitions: `admitted → executing_slice_1 → executing_slice_2 → executing_slice_3 → review_pending → certification_pending → promoted`
4. If artifact is in unexpected state, check for failed PQX slices that left it stranded
5. If still failing: escalate — do not attempt to manually advance lifecycle state

**Code path:** `spectrum_systems/govern/govern.py:lifecycle_check()`

---

### Scenario 4: EVAL Gate Failure

**Symptom:** `eval_gate BLOCK: pass_rate < threshold` or `eval_gate BLOCK: provenance missing`

**Steps:**
1. Check `eval_results.passed` / `eval_results.total` — is pass rate genuinely below threshold?
2. Check artifact has `trace_id` (required for provenance)
3. Check artifact is not flagged `execution_without_provenance`
4. If pass rate is low: check underlying eval failures in monitoring view
5. If still failing: check RCA guide cases EVAL_001–EVAL_003

**Code path:** `spectrum_systems/eval_system/eval_system.py:eval_gate()`

---

### Scenario 5: Closure Gate Block (GOV)

**Symptom:** System halted at gate; loop not advancing

**Steps:**
1. Do not bypass this gate — it is fail-closed per the system registry
2. Check that all required evidence artifacts are present
3. Check that no `failure_classification` artifacts are unresolved
4. Check event log for `control_reversal` events (high importance signal)
5. Escalate if the gate repeatedly blocks on the same evidence set

**Code path:** `spectrum_systems/modules/runtime/cde_decision_flow.py`

---

### Scenario 6: System Boundary Block (AEX)

**Symptom:** Promotion blocked at system boundary; `enforce_complete` event logged

**Steps:**
1. Do not bypass the system boundary — it is fail-closed per the system registry
2. Check `enforce_complete` event for action taken
3. Check whether block is permanent or temporary
4. Follow remediation path: failure → evidence → FRE → GOV gate → repair → retest
5. Escalate if the system boundary fires unexpectedly

**Code path:** `spectrum_systems/modules/runtime/sel_enforcement_foundation.py`

---

## Event Filtering Reference

Operators use the **operator view** by default. Switch views when needed:

| View | What you see | When to use |
|------|-------------|-------------|
| `operator_view` | Importance ≥ 3 + all monitoring events | Normal operations |
| `monitoring_view` | Monitoring-flagged events only | Dashboard / alerting |
| `debug_view` | All events | Debugging a specific failure |
| `performance_view` | EXECUTION + ENFORCE events | Latency analysis |
| `failure_view` | Failures + blocked gate decisions | RCA starting point |

All events are stored permanently. Views control display only — no data is lost.

---

## Deprecation Transition

During the 3-week migration window, old system names still work via the deprecation layer:

| Old call | New call | Warning |
|----------|----------|---------|
| `tpa_check()` | `EXECSystem.exec_check()` | DeprecationWarning emitted |
| `gov_policy()` | `GOVERNSystem.policy_check()` | DeprecationWarning emitted |
| `tlc_route()` | `GOVERNSystem.route_artifact()` | DeprecationWarning emitted |
| `wpg_gate()` | `EVALSystem.eval_gate()` | DeprecationWarning emitted |

See: `docs/migration/3ls_migration_guide.md` for the full migration timeline and steps.

---

## Escalation Matrix

| Condition | Action |
|-----------|--------|
| EXEC, GOVERN, or EVAL gate fails repeatedly on same artifact | Escalate to on-call engineer |
| CDE blocks without resolvable evidence | Escalate to platform team |
| SEL enforcement fires unexpectedly | Halt promotion; escalate immediately |
| Event log missing for a trace | Halt; do not promote; escalate |
| Deprecation warning volume > 20/hour | Begin forced migration (week 3 mode) |

---

## Key Metrics to Monitor

| Metric | Baseline | Target | Alert Threshold |
|--------|----------|--------|-----------------|
| Loop time | 45ms | 36ms | > 50ms |
| Decision reversals | 3.2% | 2.9% | > 5% |
| RCA time | 18.5min | < 10min | > 20min |
| Event usefulness | 65% | > 90% | < 80% |
| Gate false positives | 2.3% | 2.3% | > 4% |
