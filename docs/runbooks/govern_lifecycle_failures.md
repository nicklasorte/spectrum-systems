# Runbook: GOVERN Lifecycle Check Failures

**System:** GOVERN  
**Gate:** lifecycle_check  
**Failure artifact type:** structured_failure

---

## Quick Diagnosis (2 minutes)

```
FAILURE: GOVERN/lifecycle_check
WHY:  ART-001 cannot transition 'admitted' → 'promoted'
      (allowed: ['executing_slice_1'])
```

---

## Valid Lifecycle Transitions

```
admitted
  ↓
executing_slice_1
  ↓
executing_slice_2
  ↓
executing_slice_3
  ↓
review_pending
  ↓ (pass)              ↓ (issues found)
certification_pending   remediation_pending
  ↓                       ↓
promoted               certification_pending
                          ↓
                        promoted
```

---

## Pattern 1: Skipped state

**Cause:** Code attempted to transition to a state that is not reachable from the current state.

**Example:** `admitted → promoted` (skips all execution and review states)

**Fix:**
1. Check current artifact `lifecycle_state`
2. Run transitions in order — cannot skip steps
3. Each state requires its own gate to pass before advancing

---

## Pattern 2: Already promoted / terminal state

**Cause:** Artifact is already in a terminal state (`promoted`).

**Fix:**
1. Do not attempt to transition a promoted artifact
2. If re-work is needed: create a new artifact and run it through the full lifecycle
3. Never mutate a promoted artifact

---

## Pattern 3: Unknown current state

**Cause:** Artifact has a `lifecycle_state` that is not in the valid state machine.

**Fix:**
1. Check how the `lifecycle_state` was set — it must only be set by GOVERN.lifecycle_check
2. Never set `lifecycle_state` directly on an artifact
3. If corrupted: treat as a missing artifact (halt and emit finding)

---

## See Also

- `docs/runbooks/govern_policy_failures.md` — policy check failures
- `spectrum_systems/govern/govern.py` — GOVERNSystem.lifecycle_check
