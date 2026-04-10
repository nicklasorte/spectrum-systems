# GOV-B Authority Boundary Red-Team — 2026-04-09

## 1. Executive Verdict
- Is the authority model enforceable?
- **NO**

## 2. Attack Results

### Attack 1 — TLC closure leak
- **result:** **BLOCKER — succeeded**
- **explanation:** TLC is still a de facto closure decision engine because it manufactures the decisive CDE inputs instead of routing real closure evidence. In `closure_decision_pending`, TLC passes CDE a synthetic source artifact with hardcoded `blocker_count=0`, `critical_count=0`, `high_priority_count=0`, and empty unresolved actions, then sets closure booleans directly from TLC state. That lets TLC force a `lock` path whenever it wants by choosing favorable inputs, independent of true review findings. This is authority laundering: CDE signs a TLC-authored decision surface, not an independently governed one.

### Attack 2 — Non-CDE authority
- **result:** **BLOCKER — succeeded**
- **explanation:** RQX emits `review_merge_readiness_artifact` with an explicit `merge_ready` boolean and merge verdict (`safe_to_merge` vs not). That is a practical closure/readiness outcome outside CDE. The artifact naming and fields encode deploy/merge authority semantics directly. A caller can consume this artifact and bypass CDE entirely while still appearing “governed.” This is not hypothetical; the artifact is first-class, schema-validated output.

### Attack 3 — SEL without CDE
- **result:** **BLOCKER — succeeded**
- **explanation:** SEL enforces closure-like effects without requiring authoritative CDE provenance. If `execution_request.closure_lock_state` is set to `locked`, SEL blocks execution even when no valid CDE artifact is present. SEL only checks closure source strings (`cde`/`cde_only`) and optional ref presence when a closure artifact is provided; it does not require or validate a real `closure_decision_artifact` before enforcing closure-state blocking. That allows fake/incomplete closure inputs to trigger hard enforcement.

### Attack 4 — Closed-state execution leak
- **result:** **BLOCKER — succeeded**
- **explanation:** SEL only blocks when `closure_lock_state == "locked"`. If callers use `"closed"` (or any non-`locked` closed-like value), execution continues. There is no enum hard gate for closure lock state and no canonical normalization to closed/locked semantic equivalence. Result: execution can continue after a closed-state signal that should be blocking.

### Attack 5 — Next-step leakage
- **result:** **BLOCKER — succeeded**
- **explanation:** TLC rewrites CDE bounded-next-step semantics in `_real_cde` by collapsing CDE output into TLC-owned classes (`continue_repair_bounded`, `continue_bounded`, else `terminal`) instead of forwarding CDE `next_step_class` verbatim. That means TLC is substituting for CDE’s bounded-next-step classification contract. CDE may decide `hardening_required`/`final_verification_required`, but TLC repackages that into its own authority vocabulary.

### Attack 6 — Drift scenario
- **result:** **HIGH — likely recurrence without test failure**
- **explanation:** The system still exports non-CDE readiness signals (`review_merge_readiness_artifact.merge_ready`, `verdict=safe_to_merge`, PQX closure/certification artifacts) that are straightforward for wrappers/callers to misinterpret as closure authority. Existing tests verify these artifacts are produced and valid; they do not globally prevent a new wrapper from treating them as authoritative closure. Authority confusion can reappear silently through integration code while unit tests remain green.

## 3. Weakest Point
- **single most fragile component:** TLC→CDE handoff construction in `closure_decision_pending` because TLC currently controls the decisive closure evidence payload and can deterministically shape CDE outcomes.

## 4. Final Recommendation
- **DO NOT MOVE ON**
