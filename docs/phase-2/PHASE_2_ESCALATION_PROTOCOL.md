# Phase 2 Escalation Protocol

## Escalation Paths

### 1. Red Team Finding vs Implementer Disagreement

- Red Team says: "This gate doesn't block invalid input X"
- Implementer says: "X is actually valid, gate is correct"
- Escalate to: CDE
- CDE decides: move forward or fix

### 2. Test Failure

- If > 1 test fails: stop, escalate to CDE, no phase progression
- Single test failure: implementer has 1 hour to fix before escalation

### 3. Metric Miss

- If metric target missed: CDE decides (rollback or extend)
- Example: Loop latency >= 15% improvement but target was >= 20%
- CDE: extend Phase 3 or accept 15%?

### 4. Merge Conflicts

- If conflicts on shared files: CDE resolves
- Example: Phase 2.2 and Phase 2.5 both update `system_justification.py`

### 5. Scope Creep

- If phase work exceeds hours by > 20%: escalate to CDE
- CDE: extend timeline or descope feature?

## Escalation Contact

All escalations route to CDE (Canonical Decision Engine). CDE is the sole decision authority.
No implementer may self-approve a disputed finding. No progression past a blocked gate without CDE sign-off.
