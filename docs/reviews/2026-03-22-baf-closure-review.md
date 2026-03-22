# BAF Closure Review — Final Bounded Pass (2026-03-22)

## Summary judgment
**Recommendation:** closed for current roadmap stage.

This closure pass found two concrete defects that could weaken fail-closed enforcement boundaries: (1) legacy `enforce_budget_decision(...)` remained callable from non-approved callers; (2) replay result assembly still contained default status/action fallbacks that could mask malformed replay enforcement output. Both were patched narrowly and validated with targeted regression tests.

## Scope reviewed
- Runtime and replay BAF boundaries
- Control integration boundary handling of enforcement decisions
- Legacy enforcement entrypoint reachability
- Downstream replay/reporting translation points that consume `decision` / `final_status`
- Existing BAF-focused tests

## Files inspected
- `spectrum_systems/modules/runtime/replay_engine.py`
- `spectrum_systems/modules/runtime/control_integration.py`
- `spectrum_systems/modules/runtime/enforcement_engine.py`
- `spectrum_systems/modules/runtime/evaluation_control.py`
- `spectrum_systems/modules/runtime/control_executor.py`
- `spectrum_systems/modules/runtime/evaluation_auto_generation.py`
- `spectrum_systems/modules/runtime/replay_decision_engine.py`
- `spectrum_systems/modules/runtime/evaluation_enforcement_bridge.py`
- `tests/test_enforcement_engine.py`
- `tests/test_replay_engine.py`

## Findings by category
### A. Downstream decision weakening audit
- **Defect found:** replay result builder in BAG path used fallback defaults (`deny`, `deny_execution`) when constructing replay artifacts. This could hide malformed/missing values instead of hard-failing.
- **Action:** removed fallback defaulting and added explicit allowlist validation for replay/original action/status and replay decision vocabulary; unknown values now raise `ReplayEngineError`.

### B. Legacy-path closure audit
- **Defect found:** `enforce_budget_decision(...)` in `enforcement_engine.py` could be reached by any caller importing it, not only explicit legacy surfaces.
- **Action:** added explicit caller-boundary guard; function now raises `EnforcementError` outside approved legacy callers/test modules.

### C. Final status end-to-end audit
- Audited decision vocabulary path (`allow` / `deny` / `require_review`) across evaluation control, enforcement, control integration, and replay.
- No additional hidden acceptance or coercion found after replay default-removal patch.

### D. Contract and artifact closure audit
- Audited only as needed for patched defects. No schema/example/manifest mismatch requiring churn was identified.

## Changes made
1. Restricted legacy enforcement entrypoint calls to explicitly approved callers/test modules (hard-fail otherwise).
2. Removed replay result default coercions and added strict decision/status/action allowlist checks.
3. Added regression tests for both defects.

## Tests run with exact results
- `pytest tests/test_enforcement_engine.py tests/test_replay_engine.py`
  - **Result:** 36 passed, 0 failed.
- `PLAN_FILES='docs/review-actions/PLAN-BAF-CLOSURE-2026-03-22.md spectrum_systems/modules/runtime/enforcement_engine.py spectrum_systems/modules/runtime/replay_engine.py tests/test_enforcement_engine.py tests/test_replay_engine.py docs/reviews/2026-03-22-baf-closure-review.md' .codex/skills/verify-changed-scope/run.sh`
  - **Result:** `[OK] All changed files are within declared scope.`

## Residual risks
- A legacy approved caller (`control_executor`) still exists by design for backward-compatible paths. This remains constrained but is technical debt.
- Replay legacy helper paths (`replay_run`) still include compatibility mappings for historical decision surfaces; they are bounded but should be retired at next maturity gate.

## Reopen triggers
Reopen BAF closure work if any of the following occurs:
1. New artifact types are admitted into runtime/replay control paths.
2. Any downstream adapter introduces status remapping/defaulting for enforcement decisions.
3. Additional non-approved callers are introduced for legacy `enforce_budget_decision(...)`.
4. Contracts for `evaluation_control_decision`, `enforcement_result`, or `replay_result` change vocabulary semantics.
5. A production incident shows enforcement ambiguity, downgrade, or silent permissive behavior.

## Commit hash
`0e9c559`
