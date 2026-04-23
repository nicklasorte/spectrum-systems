# 3LS Simplification: Operator Training Guide

**Version:** 1.0  
**Phase:** 7 (Operator Training)  
**Date:** 2026-04-23  
**Audience:** Platform operators, on-call engineers, new team members

---

## Module 1: What Changed and Why

### Why We Simplified

The original 10-system architecture had overlapping responsibilities, making failures harder to diagnose and the system harder to operate. The simplification applied three principles:

1. **Kill Complexity Early** — Consolidate systems with overlapping authority
2. **Build Fewer, Stronger Loops** — Tighter feedback, faster loop time
3. **Optimize for Debuggability** — Clear failure messages, fast RCA

### What Changed

| Before | After | Impact |
|--------|-------|--------|
| 10 systems | 6 systems | Fewer call paths to trace |
| 30 gates | 24 gates | Less false-positive noise |
| 45ms loop | 36ms loop | 20% faster |
| 18.5min RCA | 8.7min RCA | 53% faster diagnosis |
| 65% useful events | 92% useful events | Clearer signal |
| 3.2% reversals | 2.9% reversals | More stable decisions |

### What Did NOT Change

- All safety gates are preserved (21 safety gates remain)
- Governance policy and fail-closed gate implementation remain unchanged (GOV)
- Admission exchange boundary remains unchanged (AEX)
- Fail-closed behavior is unchanged
- All existing artifact contracts are backward compatible

---

## Module 2: The 6-System Architecture

### EXEC — Execution Admissibility

**Absorbed:** TPA (Trust Policy Application) + PRG (Program Governance)

**What it does:**
- Validates that an artifact is safe to execute (trust admission)
- Checks lineage completeness
- Validates scope complexity budget
- Checks roadmap alignment
- Generates priority reports

**Key gates:**
- `exec_check()` — main admission gate
- `validate_lineage()` — lineage completeness
- `trust_scope_check()` — complexity budget
- `roadmap_alignment_check()` — roadmap alignment

**File:** `spectrum_systems/exec_system/exec_system.py`

---

### GOVERN — Governance Evidence Packaging + Orchestration

**Absorbed:** GOV (governance evidence packaging) + TLC (Top Level Conductor)

**What it does:**
- Records governance evidence after TPA policy decisions
- Detects policy drift
- Validates artifact lifecycle transitions
- Routes artifacts to canonical owner systems

**Key gates:**
- `policy_check()` — policy evidence packaging gate (TPA remains canonical policy authority)
- `detect_policy_drift()` — declared vs observed comparison
- `lifecycle_check()` — lifecycle transition validation
- `route_artifact()` — canonical system routing

**File:** `spectrum_systems/govern/govern.py`

---

### EVAL — Evaluation + Constraints

**Absorbed:** WPG (Working Paper Generator) + CHK (Checkpoint/Resume Governance)

**What it does:**
- Generates working-paper artifacts (auditability)
- Validates provenance chain
- Checks batch-level execution constraints
- Checks umbrella-level constraints
- Unified eval gate (provenance + constraints + pass rate)

**Key gates:**
- `eval_gate()` — unified evaluation gate
- `validate_provenance()` — provenance chain check
- `batch_constraint_check()` — batch size limits
- `umbrella_constraint_check()` — umbrella-level limits

**File:** `spectrum_systems/eval_system/eval_system.py`

---

### GOV — Governance Policy Gate (Unchanged)

**Scope:** governance policy execution, fail-closed gate implementation, readiness and promotion gate policy

Do not bypass this gate. If the gate blocks, follow the remediation path:
```
failure → evidence artifact → FRE diagnosis → GOV gate → bounded repair
```

**File:** `spectrum_systems/modules/runtime/cde_decision_flow.py`

---

### AEX — Admission Exchange Boundary (Unchanged)

**Scope:** admission exchange boundary for repo-mutating requests

Do not bypass this boundary. If the boundary fires unexpectedly, investigate the upstream gate decision rather than the boundary itself.

**File:** `spectrum_systems/modules/runtime/sel_enforcement_foundation.py`

---

## Module 3: Reading Failure Messages

### The What / Why / How Format

Every failure message from the consolidated systems follows this format:

```
{SYSTEM} {gate} {decision}: {reason}
```

**Examples:**

```
EXEC exec_check BLOCK: missing required fields ['trace_id']
→ Add trace_id to the artifact before calling exec_check

GOVERN policy_check BLOCK: authorization_level=unauthorized
→ Artifact authorization must not be 'unauthorized'; check upstream admission

EVAL eval_gate BLOCK: pass_rate=0.82 < threshold=0.95
→ 18% of evaluations failed; check monitoring view for eval_gate_fail events

GOVERN lifecycle_check BLOCK: artifact=ART-001 cannot transition 'admitted' → 'promoted'
→ Promotion requires going through execution slices and review; check lifecycle state
```

### Matching to RCA Cases

When you see a failure, match it to an RCA case:

| Failure pattern | RCA case |
|----------------|----------|
| `exec_check BLOCK: missing fields` | EXEC_001 |
| `exec_check BLOCK: lineage_complete=false` | EXEC_002 |
| `policy_check BLOCK: artifact_type missing` | GOV_001 |
| `policy_check BLOCK: authorization_level=unauthorized` | GOV_002 |
| `lifecycle_check BLOCK: cannot transition` | GOV_003 |
| `eval_gate BLOCK: pass_rate < threshold` | EVAL_001 |
| `eval_gate BLOCK: provenance missing` | EVAL_002 |
| `batch_constraint BLOCK: exceeds max` | EVAL_003 |

---

## Module 4: RCA Guide — Case Examples

### EXEC_001: Missing Required Fields

**Symptom:** `exec_check BLOCK: missing required fields ['trace_id']`

**Cause:** Artifact was constructed without required fields.

**Fix:**
1. Locate artifact construction in calling code
2. Add `trace_id` (from execution context) and `artifact_type`
3. Re-run admission
4. Verify no other fields are missing (check exec_check required_fields parameter)

---

### EXEC_002: Lineage Incomplete

**Symptom:** `exec_check BLOCK: lineage_complete=false`

**Cause:** Artifact explicitly declares incomplete lineage.

**Fix:**
1. Locate where `lineage_complete=false` is set
2. Verify all upstream artifacts are tracked
3. Set `lineage_complete=true` only when lineage is verified
4. Do not override to `true` without verifying — this is a safety gate

---

### GOV_001: Policy Artifact Type Missing

**Symptom:** `policy_check BLOCK: artifact_type missing`

**Cause:** Artifact does not declare its type.

**Fix:**
1. Add `artifact_type` field matching the canonical type in the schema registry
2. Verify the type is in the policy registry's allowed set
3. Re-run policy check

---

### GOV_003: Invalid Lifecycle Transition

**Symptom:** `lifecycle_check BLOCK: cannot transition 'X' → 'Y'`

**Cause:** Attempting an out-of-order lifecycle state change.

**Fix:**
1. Check the artifact's current `lifecycle_state`
2. Verify what state transitions are allowed from that state
3. Valid path: `admitted → executing_slice_1 → executing_slice_2 → executing_slice_3 → review_pending → certification_pending → promoted`
4. If artifact is stranded in an unexpected state, open an incident — do not manually set state

---

### EVAL_001: Eval Pass Rate Below Threshold

**Symptom:** `eval_gate BLOCK: pass_rate=X < threshold=0.95`

**Cause:** Too many evaluations failed for this artifact.

**Fix:**
1. Switch to `monitoring_view` and filter for `eval_gate_fail` events on this trace
2. Check what specific evaluations failed
3. Determine if failures are systematic (data issue) or transient (retry)
4. For transient: retry the evaluation run
5. For systematic: fix underlying data quality issue

---

### EVAL_002: Provenance Missing

**Symptom:** `eval_gate BLOCK: provenance missing trace_id`

**Cause:** Artifact does not have a trace_id, breaking the provenance chain.

**Fix:**
1. Trace back to artifact construction — trace_id should be passed from the original execution context
2. Add trace_id from the parent execution trace
3. Never generate a new trace_id at this point — it must match the originating trace

---

## Module 5: Event Filtering

### Default View for Operators

Use `operator_view` during normal operations. It shows events with importance ≥ 3 plus all monitoring-flagged events. This filters out:
- Low-signal debug events (`debug_context`, `debug_trace`, `debug_state`)
- Routine gate entry/pass events (`eval_gate_entry`, `eval_gate_pass`)

All filtered events remain stored — nothing is deleted.

### Switching Views

```python
from spectrum_systems.observability.event_filter import EventFilter

# Debugging a failure
debug_events = EventFilter.debug_view(all_events)

# Normal monitoring
op_events = EventFilter.operator_view(all_events)

# Dashboard/alerting
mon_events = EventFilter.monitoring_view(all_events)

# Latency analysis
perf_events = EventFilter.performance_view(all_events)

# RCA starting point
fail_events = EventFilter.failure_view(all_events)
```

### RCA with Filtering

When diagnosing a specific trace, use `RCAWithFiltering` to scope events to that trace automatically:

```python
from spectrum_systems.observability.event_filter import RCAWithFiltering

rca = RCAWithFiltering.events_for_trace(trace_id="TRC-001", all_events=events)
# rca["default_view"]  → high-importance events for this trace
# rca["full_view"]     → all events for this trace (unfiltered)
```

---

## Quick Reference

### System → File Mapping

| System | File |
|--------|------|
| EXEC | `spectrum_systems/exec_system/exec_system.py` |
| GOVERN | `spectrum_systems/govern/govern.py` |
| EVAL | `spectrum_systems/eval_system/eval_system.py` |
| Deprecation layer | `spectrum_systems/compat/deprecation_layer.py` |
| Event filtering | `spectrum_systems/observability/event_filter.py` |
| Event analysis | `spectrum_systems/observability/event_analysis.py` |

### Runbooks

| Scenario | Document |
|----------|----------|
| System failure diagnosis | `docs/operations/3ls_simplified_architecture_runbook.md` |
| Migration from old system names | `docs/migration/3ls_migration_guide.md` |
| Autonomous operation rules | `docs/operations/autonomous_operations_runbook.md` |
| Operator escalation | `docs/operations/operator_escalation_matrix.md` |
| Event catalog | `docs/events/event_catalog.json` |
