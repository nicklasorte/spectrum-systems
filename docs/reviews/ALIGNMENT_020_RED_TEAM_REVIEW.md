# ALIGNMENT_020 — Red Team Review

**Review ID:** ALIGNMENT-020  
**Reviewer:** Claude (Staff Architect — Opus 4.6, Red-Team Stance)  
**Date:** 2026-04-01  
**Scope:** System integrity, failure-mode analysis, bypass detection across the full Spectrum Systems governance architecture  
**Verdict:** CONDITIONAL FAIL — multiple bypass paths and false-pass scenarios remain exploitable  

---

## 1. Top 5 Structural Risks

1. **Enforcement action recording is `present_but_bypassable` — the system's own gap classification confirms this.** The April 1, 2026 ROADMAP-REEVALUATION-018 foundation gap table explicitly classifies "enforcement action recording" as `present_but_bypassable`. A canonical enforcement path exists alongside a "constrained legacy compatibility mapper," meaning there are at least two enforcement paths in production, and one of them is not fully governed. The system cannot claim non-bypassable enforcement while its own foundation audit says otherwise.

2. **Dual/parallel decision authority across control surfaces.** Control decisions are made by multiple modules: `evaluation_control.py`, `control_loop.py`, `enforcement_engine.py`, `decision_gating.py`, `judgment_engine.py`, the replay governance gate, the baseline gate, and the release canary. Despite a declared precedence rule (`rollback > block/freeze > hold > warn > promote`), there is no single runtime authority module that all surfaces are required to route through. RE18-08 ("Consolidate control decision precedence rules into one runtime authority module") is still `planned` — meaning the fragmentation is real and live.

3. **Control Loop Closure Gate (CL-01 through CL-05) has NOT passed.** The system roadmap's own hard-gate readiness assessment says "NOT READY" with all eight enhanced gate checks rated `partial`. Every CL condition — failure binding, deterministic policy consumption, behavior-changing control, recurrence prevention, longitudinal calibration, calibration lifecycle influence, replay reconstruction, and falsification — is incomplete. The system claims to be certification-gated but the certification gate's own pass conditions are themselves not yet fully enforced.

4. **Replay governance defaults to `require_replay: false` and `missing_replay_action: allow`.** The default replay governance policy allows execution to proceed when replay evidence is entirely absent. This means the "replayable" invariant is not enforced by default — it is opt-in. Any path that does not explicitly set `require_replay: true` operates without replay governance, and the system silently marks `replay_governed: false` and allows continuation.

5. **SF-07 eval coverage is report-only, not enforcement.** The eval coverage and slice summary system (SF-07) is explicitly documented as "reporting/visibility, not a replacement for SF-05 CI gating." The `--blocking-on-gaps` flag is described as "optional blocking mode (for future wiring)." This means required-slice coverage gaps are observed and logged but do not actually block execution or promotion in the current system. A critical slice can be failing while low-risk slices pass, and nothing stops promotion.

---

## 2. Bypass Opportunities

### Bypass 1: Legacy enforcement path via replay_run

**Steps:**
1. Execute a governed run through the canonical `eval_summary → evaluation_control_decision → enforcement_result` chain.
2. Trigger a replay via `replay_run()`.
3. `replay_run()` routes through `validate_and_emit_decision → build_validation_budget_decision → enforce_budget_decision` — the legacy budget pathway, NOT the canonical chain.
4. The replay uses a different enforcement function with different decision semantics.
5. A run that would be blocked by canonical enforcement can pass through replay enforcement with different outcomes.

**Status:** Identified in the 2026-03-22 control-loop enforcement review (CF-4). RE18-01 and RE18-02 are planned to fix this. Not yet fixed.

### Bypass 2: Threshold override via unchecked caller parameter

**Steps:**
1. Call `build_evaluation_control_decision` with a custom `thresholds` dict.
2. The function merges the caller-supplied thresholds over `DEFAULT_THRESHOLDS`.
3. Set all thresholds to permissive values (e.g., `pass_rate_threshold: 0.0`).
4. The control decision emits `allow` regardless of actual quality.
5. No governance token or audit artifact is required for threshold relaxation.

**Status:** Identified in the 2026-03-22 control-loop enforcement review. The parameter is still on the public surface.

### Bypass 3: Missing replay evidence with default policy

**Steps:**
1. Run any execution path without producing a replay artifact.
2. The replay governance gate checks `require_replay` in policy.
3. Default policy has `require_replay: false`.
4. The gate returns `system_response: allow` with `rationale_code: replay_not_required`.
5. Execution proceeds without any replay validation or reproducibility proof.
6. The artifact records `replay_governed: false` — the system self-documents that replay governance was skipped, but does not block.

**Status:** By design in the default policy. The system is "replayable" only when callers explicitly opt in.

### Bypass 4: Eval coverage gap without enforcement

**Steps:**
1. Deploy a change that removes eval cases for a critical slice.
2. SF-07 reports the gap in `eval_coverage_summary.json` with `required_slice_gaps`.
3. SF-05 CI gate runs but only checks pass/fail on existing cases — it does not check that required slices have minimum coverage.
4. SF-07's `--blocking-on-gaps` is not wired into CI.
5. The change passes CI and is promotable with zero coverage on a critical slice.

**Status:** Documented as future work. The blocking mode is not yet wired.

### Bypass 5: Certification structural completeness without behavioral proof

**Steps:**
1. Assemble all required certification artifacts (chaos summary, test results, review artifacts, review validation).
2. All four certification checks pass because they test structural properties (do tests pass? do review artifacts validate?).
3. None of the four checks verify that the control loop actually changes behavior in response to failures.
4. The certification pack emits `certification_status=certified, decision=pass`.
5. Promotion proceeds despite the system never proving that a failure caused a policy change, a block, or a prevention action.

**Status:** The certification pack explicitly states it "does not certify broad repository health outside the four required checks" or "architectural compliance outside existing canonical validators." Behavioral proof is outside its scope.

---

## 3. False-Pass Scenarios

### False-Pass A: CL-01 (Failure Binding) appears satisfied without enforcement

CL-01 requires `failure → eval case → policy linkage`. The system can produce:
- A failure classification artifact
- An eval case linked to that failure
- A policy document referencing the failure class

These three artifacts satisfy the structural proof requirement. However, nothing currently requires that the policy reference actually changes a control decision. The failure can be classified, an eval case can be added, the policy can mention it, and yet the next identical failure passes through with `allow`. RE18-04 and RE18-05 are planned to close this but are `planned`, not implemented.

### False-Pass B: Hard-gate passes with `partial` classifications

The hard-gate certification checks test for artifact presence and schema validity. The system's own foundation gap classification shows every layer as `present_but_partial` or worse. But the certification artifacts for individual slices can pass while the end-to-end chain remains partial. The certification gate certifies slices, not the integrated chain.

### False-Pass C: Deterministic IDs mask non-deterministic behavior

The system replaced `uuid4()` with deterministic ID generation (e.g., from `run_id` + `eval_run_id`). This makes artifacts appear replay-stable. However, deterministic IDs do not prove deterministic decisions. If the control function has any path where inputs are evaluated in non-deterministic order (e.g., dict iteration in Python < 3.7 equivalents, or floating-point comparison edge cases in threshold evaluation), the ID will be the same but the decision may differ. The ID stability creates a false sense of determinism.

### False-Pass D: `not-yet-evaluable` status defers without blocking

The evaluation status vocabulary includes `not-yet-evaluable`, which "does not block a run from being recorded." A system in `not-yet-evaluable` status can persist in this state indefinitely without triggering any enforcement. It is explicitly not a failure, so it does not trigger fail-closed behavior. It is a legitimate permanent non-evaluation.

---

## 4. Inconsistency Map

### 4.1 Enforcement vocabulary fragmentation

| Surface | Decision vocabulary |
| --- | --- |
| Control loop (SF-05/SF-11) | `allow`, `warn`, `freeze`, `block` |
| Enforcement bridge/action schema | `allow_with_warning`, `freeze_changes`, `block_release`, `require_review` |
| Replay governance | `allow`, `require_review`, `quarantine`, `block` |
| Release/canary (SF-14) | `promote`, `hold`, `rollback` |
| Baseline gating (SRE-06) | `pass`/`allow`, `flag`, `block_promotion` |
| HITL override | `allow_once`, `deny`, `require_rerun`, `require_revision` |

Six different decision vocabularies across six surfaces. The `quarantine` response from replay governance has no equivalent in the control loop vocabulary. The `require_review` response exists in both replay governance and the legacy enforcement bridge but with different semantics. `freeze` vs `freeze_changes` vs `hold` are three terms for a similar concept across different surfaces. No canonical mapping artifact exists that proves these vocabularies are semantically consistent.

### 4.2 PQX vs control vs promotion disagreements

- PQX evaluates two pre-execution gates (contract impact + execution change impact) and blocks on failure.
- The control loop evaluates eval summaries and emits allow/warn/freeze/block.
- Promotion evaluates certification artifacts and blocks on missing/failed certification.
- These three surfaces can reach different conclusions about the same slice at the same time because they evaluate different evidence sets with different decision functions.
- RE18-09 ("Add cross-surface consistency suite") is planned to test for this. It does not yet exist.

### 4.3 Multiple preflight/admission surfaces

Preflight checks exist in at least three locations:
- PQX slice runner preflight (manifest completeness + contract impact + execution change impact)
- Strategy compliance hard gate (10-item checklist)
- Control loop admission (eval summary → control decision)

These are not unified. A change can pass PQX preflight but fail the strategy compliance hard gate, or vice versa, because they check different conditions with no reconciliation protocol.

---

## 5. Most Dangerous Blind Spot

**The system has no mechanism to verify that enforcement actually changes outcomes.**

Every artifact, schema, gate, and governance surface in the system is structural. They verify that:
- artifacts exist
- artifacts are schema-valid
- artifacts contain required fields
- decisions follow declared precedence

None of them verify that:
- A failure that caused a `block` decision actually prevented the blocked action from occurring
- A policy change that resulted from a failure actually caused different behavior on the next occurrence
- A freeze that required remediation actually resulted in different outputs after remediation

The system proves that enforcement artifacts are produced. It does not prove that enforcement artifacts are consumed and obeyed. The gap between "enforcement decision emitted" and "enforcement decision obeyed" is the single largest unmonitored surface in the architecture. A downstream consumer of an enforcement artifact can receive `block`, log it, and proceed anyway — and nothing in the current architecture detects this.

This is compounded by the fact that the system is a design-first documentation repository. There is no production runtime where enforcement decisions are actually executed against real process control. The enforcement chain terminates at artifact production, not at process termination. The system proves it can produce the right decision. It does not prove the decision is effective.

---

## 6. Hard-Gate Integrity Assessment

**FAIL**

Reasoning:

1. The system's own ROADMAP-REEVALUATION-018 assessment (embedded in the system roadmap, dated April 1, 2026) rates the Control Loop Closure Gate as **NOT READY** with all eight checks at `partial`.

2. The enforcement action recording layer is self-classified as `present_but_bypassable` — the one classification that directly contradicts the "non-bypassable" invariant.

3. The certification pack tests four structural checks. None test behavioral enforcement effectiveness. Falsification tests for CL conditions (RE18-07) are `planned` but do not yet exist.

4. The hard-gate checklist in `strategy_compliance_hard_gate.md` requires 10 items all marked YES to pass. Multiple items cannot currently be satisfied:
   - "Replayability satisfied?" — default policy does not require replay.
   - "Drift detection run?" — drift checks exist but are not mandatory on all progression surfaces.
   - "Certification ready?" — certification scope is narrow and does not cover CL proof conditions.

5. Planned remediation steps (RE18-01 through RE18-24) are all `planned`. Zero are `complete`. The hard gate is designed correctly but not yet implementable with current evidence.

---

## 7. Should This System Scale?

**NO**

Reasoning:

1. **The system's own governance says NO.** The hard foundation-first gate rule states: "No roadmap may advance broader capability if required foundation layers are missing, partial, ambiguous, or bypassable." Multiple layers are partial or bypassable. The system's own rules prohibit scaling.

2. **Enforcement is structurally present but operationally disconnected.** The enforcement chain produces artifacts that declare decisions. Nothing verifies those decisions are consumed. Scaling a system where enforcement is advisory-by-outcome (even if mandatory-by-artifact) amplifies the gap between what the system claims and what it achieves.

3. **Cross-surface consistency is untested.** Six different decision vocabularies, three different preflight surfaces, and multiple decision authorities mean that scaling adds combinatorial inconsistency risk. RE18-08 and RE18-09 must be complete before scale.

4. **The learning loop is not closed.** CL-01 through CL-05 are all partial. Failures are captured but not provably enforced. Calibration exists but does not provably influence lifecycle decisions. Scaling a system with an open learning loop means scaling a system that cannot self-correct.

5. **Replay is opt-in, not mandatory.** The "replayable" invariant is a policy choice, not a system guarantee. Scaling with opt-in replay means scaling a system where reproducibility coverage is unknown and unenforceable.

The system should stabilize the single dominant sequential path, close the CL-01 through CL-05 gate with behavioral (not just structural) proof, unify decision authority, and wire SF-07 blocking mode before any expansion.

---

## Appendix: Risk Summary Table

| # | Risk | Severity | Category | Current Status |
| --- | --- | --- | --- | --- |
| R-1 | Enforcement path bypass via legacy compatibility mapper | Critical | Bypass | Known, unresolved (RE18-01/02 planned) |
| R-2 | Control decision authority fragmented across 6+ modules | Critical | Inconsistency | Known, unresolved (RE18-08 planned) |
| R-3 | CL gate NOT READY — all conditions partial | Critical | Hard-gate | Self-assessed, blocking expansion |
| R-4 | Replay governance off by default | High | Bypass | By design, policy-configurable |
| R-5 | Eval coverage gaps non-blocking | High | False-pass | SF-07 blocking mode not wired |
| R-6 | Certification tests structural completeness, not behavioral proof | High | False-pass | RE18-06/07 planned |
| R-7 | Six incompatible decision vocabularies across surfaces | High | Inconsistency | No canonical mapping exists |
| R-8 | Threshold override parameter on public surface | Medium | Bypass | Identified in review, unresolved |
| R-9 | `not-yet-evaluable` as permanent non-failure state | Medium | False-pass | By design |
| R-10 | No verification that enforcement decisions are obeyed | Critical | Blind spot | Architectural gap |

---

*This review is a point-in-time adversarial assessment. Findings reflect repository state as of 2026-04-01. This review does not propose redesigns; it identifies failure modes and bypass paths that must be closed before the system can credibly claim its stated invariants.*
