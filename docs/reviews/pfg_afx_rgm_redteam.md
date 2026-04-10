# PFG/AFX/RGM Red-Team

## Executive Verdict
YES

## Attack Results

### Attack 1 — Preflight bypass
**Result:** Blocked.  
**Explanation:** `run_governed_autofix(...)` now computes preflight and enforces `enforce_preflight_gate(...)` before any mutation/validation replay/commit branch, so execution cannot continue without `ALLOW`.

### Attack 2 — Fail-open ALLOW/BLOCK
**Result:** Blocked.  
**Explanation:** `strategy_gate_decision != ALLOW` raises `preflight_strategy_gate_blocked`; overdue governance risk also adds invariant violation and raises `review_governance_signal_overdue_blocked`.

### Attack 3 — Validation drift
**Result:** Blocked.  
**Explanation:** `run_validation_replay(...)` uses only `scripts/run_review_artifact_validation.py` and no alternate command paths; CI/autofix/governed execution converge to one validation entrypoint.

### Attack 4 — Missing artifact tolerance
**Result:** Blocked.  
**Explanation:** artifact spine enforcement requires `build_admission_record`, `validation_result_record`, and `repair_attempt_record` before progression.

### Attack 5 — Governance blind spot
**Result:** Blocked.  
**Explanation:** governance radar scans review registry and classifies `OK/WARNING/OVERDUE`, including missing due dates and stale overdue windows in `review_governance_signal_artifact`.

### Attack 6 — Governance bypass
**Result:** Blocked.  
**Explanation:** preflight consumes governance signal; `risk_level == OVERDUE` triggers hard block/fail-closed before execution continuation.

## Weakest Point
Registry quality remains a dependency: malformed review records can reduce diagnostic richness. However, malformed/missing registry data still blocks fail-closed in governed autofix path.

## Final Recommendation
SAFE TO MOVE ON
