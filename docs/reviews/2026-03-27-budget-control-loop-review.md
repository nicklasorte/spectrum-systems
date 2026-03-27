# FPO Review: Budget-Aware Control-Loop Slice (SRE-09 / SRE-10)

## 1. Review Metadata

| Field | Value |
|---|---|
| Review ID | 2026-03-27-budget-control-loop-review |
| Review Date | 2026-03-27 |
| Repository | spectrum-systems |
| Reviewer | Claude (Reasoning Agent — Sonnet 4.6) |
| Review Type | FPO (Fit-for-Purpose-Only) — targeted correctness review |
| Commit / Slice | SRE-09 / SRE-10 merged budget-aware control-loop slice |
| Prior Review Referenced | 2026-03-22-control-loop-enforcement-review |

**Inputs consulted:**
- `spectrum_systems/modules/runtime/control_loop.py`
- `spectrum_systems/modules/runtime/evaluation_control.py`
- `spectrum_systems/modules/runtime/control_integration.py`
- `spectrum_systems/modules/runtime/agent_golden_path.py` (budget construction path)
- `tests/test_control_loop_chaos.py`
- `tests/test_eval_ci_gate.py`
- `tests/helpers/replay_result_builder.py`
- `contracts/schemas/evaluation_control_decision.schema.json`
- `docs/design-review-standard.md`
- `docs/review-to-action-standard.md`

---

## 2. Scope

**In scope:**
- Whether `error_budget_status` is enforced as a true runtime contract input.
- Correctness and completeness of `observability_metrics` / `error_budget_status` consistency checks.
- Semantic correctness of the budget warning / exhausted / invalid → control decision mappings.
- Eval CI gate coherence after budget-aware blocking was introduced.
- Whether chaos tests validate real runtime invariants or mirror implementation details.
- Policy logic duplication across `control_loop.py`, `evaluation_control.py`, and the CI gate.
- Fail-open, ambiguity, drift, and policy-conflict risks.

**Out of scope:**
- `enforcement_engine.py` internals (reviewed separately).
- Override / HITL path (not modified in this slice).
- Full `agent_golden_path.py` pipeline beyond the budget construction function.
- Chaos scenario fixture JSON content (file not in the scope list; its runner behavior is in scope).

---

## 3. Executive Summary

- **Verdict: PASS WITH FINDINGS.** The slice establishes `error_budget_status` as a genuine runtime contract input with multi-layer validation and introduces a coherent budget-to-decision mapping. The basic architecture is sound.
- **One critical defect exists**: the budget `warning` override unconditionally replaces any prior control decision with `require_review`, which can downgrade a `deny` (e.g., from `trust_breach` or `stability_breach`) to a softer outcome. This is a fail-open governance regression.
- **The consistency check between `observability_metrics` and `error_budget_status` is conditional**: it only fires when both sides have a matching entry, so it can be silently bypassed by omitting a metric from either side.
- **The test builder (`align_replay_budget_with_observability`) does not recalculate `budget_status`**: chaos precedence tests therefore operate with a frozen "healthy" budget state regardless of injected metric values, leaving budget-aware decision paths untested in the chaos suite.
- **No test directly exercises budget warning / exhausted / invalid states through the eval CI gate.**
- The exhausted and invalid budget mappings are semantically correct and fail-closed.
- The slice is safe to build on after the critical defect (F-1) is fixed and the coverage gaps (F-3, F-4) are addressed.

---

## 4. Maturity Assessment

Not a full maturity review. This is a targeted FPO slice assessment.

The budget-aware control path adds a needed governance dimension. The multi-layer enforcement structure (`control_integration.py` → `control_loop.py` → `evaluation_control.py`) is well-layered. Schema validation at the `evaluation_control.py` layer is rigorous. The primary maturity gaps are in test completeness and a semantic defect in the warning override logic.

---

## 5. Strengths

- **`error_budget_status` is enforced at three independent layers**: presence check at `control_integration.py:239`; structural + consistency validation in `control_loop.py:_validate_replay_budget_inputs`; full schema validation in `evaluation_control.py:_to_eval_summary_from_replay_result`. This is defence-in-depth.
- **Full schema validation of embedded artifacts**: `evaluation_control.py` runs `load_schema("error_budget_status")` and `load_schema("observability_metrics")` as hard preconditions. Malformed embedded artifacts cannot produce a decision.
- **Trace linkage is enforced**: `observability_metrics.trace_refs.trace_id`, `error_budget_status.trace_refs.trace_id`, and `error_budget_status.observability_metrics_id` are all cross-validated against the parent `replay_result`. A tampered or mis-assembled artifact cannot pass.
- **Budget exhausted and invalid states are correctly fail-closed**: `exhausted` → `deny` with `freeze` or escalated `block`; `invalid` → `deny` with `block`. No ambiguity, no recover path.
- **`_deterministic_decision_id` incorporates budget signals**: budget signals appended to `triggered_signals` inside `_apply_budget_status_override` are part of the decision ID seed, so budget-affected decisions have distinct identifiers.
- **Eval CI gate correctly routes through `build_evaluation_control_decision`** with `replay_result` as the input type, not `eval_summary`. The test `test_gate_invokes_runtime_control_with_replay_result` confirms this.
- **`control_integration.py:239` guards the integration boundary**: if a `replay_result` artifact arrives at the gate without `error_budget_status`, it is rejected before any control logic executes.
- **`agent_golden_path.py` derives budget state from live metric values**, not from a static fixture, using the same consumption-ratio logic as production code. This means the golden path exercises real budget state transitions.

---

## 6. Structural Gaps

**G-1. No test exercises budget states through the eval CI gate.**
`test_eval_ci_gate.py` has no test that supplies a `replay_result` with `budget_status="warning"`, `"exhausted"`, or `"invalid"` and asserts that the gate blocks or escalates correctly. Budget-aware CI gate behavior is tested only by implication via `control_decision_blocked` reasons.

**G-2. `align_replay_budget_with_observability` does not recalculate `budget_status`.**
The helper updates `observed_value` fields inside `error_budget_status.objectives`, but leaves `budget_status`, `highest_severity`, and `triggered_conditions` unchanged. After patching metrics in the chaos tests, the budget status stays at the example fixture's "healthy" value. Budget-aware decision paths are therefore unreachable in the chaos precedence tests.

**G-3. `highest_severity` vs `budget_status` consistency check is one-directional.**
`_validate_replay_budget_inputs` raises if `highest_severity > budget_status` (a worst-objective worse than the overall — semantically impossible). It does not raise if `budget_status > highest_severity` (the overall budget claims worse than any individual objective). A `budget_status="exhausted"` artifact with all objectives at `status="healthy"` passes validation silently.

**G-4. The consistency check between `observability_metrics.metrics` and `error_budget_status.objectives.observed_value` is conditional.**
The check in `control_loop.py:116–125` fires only when the metric key exists in both `metrics` and in an objective entry with the same `metric_name`. If a metric is present in observability but has no matching objective, or if the objective is absent, the check silently skips. An artifact can claim inconsistent values and not be caught.

---

## 7. Risk Areas

**R-1. CRITICAL — Budget warning unconditionally downgrades deny.**
In `evaluation_control.py:_apply_budget_status_override`, the `budget_status == "warning"` branch always returns `("warning", "warn", "require_review", "require_review_budget_warning")`, overriding whatever the prior evaluation computed. This means:

- `stability_breach` → `(exhausted, freeze, deny, deny_stability_breach)` + budget warning → `(warning, warn, require_review, require_review_budget_warning)` — **deny downgraded to require_review**
- `trust_breach` → `(blocked, block, deny, deny_trust_breach)` + budget warning → `(warning, warn, require_review, require_review_budget_warning)` — **deny downgraded to require_review**
- `indeterminate_failure` alone → `deny` + budget warning → `require_review` — **deny downgraded**

The intent was likely to escalate healthy signals to require_review when budget is at warning. Instead, the override weakens prior deny decisions. This is a **fail-open governance regression**: a system in trust breach or stability breach can proceed to human review (potentially allow after review) rather than being hard-denied.

Severity: **Critical**. Exploitable via any artifact where budget is at warning and evaluation signals would otherwise deny.

**R-2. HIGH — `highest_severity < budget_status` is not validated.**
See G-3. An artifact with `budget_status="exhausted"` and all objectives at "healthy" would pass the `_validate_replay_budget_inputs` check. The exhausted-state control behavior would then activate for an artifact that has no supporting objective evidence. The budget would effectively be synthetic.

**R-3. MEDIUM — Partial schema validation in `control_loop.py` can drift from the schema.**
`_validate_replay_budget_inputs` checks a manually-specified subset of `error_budget_status` fields rather than running `load_schema("error_budget_status")`. If the schema evolves (new required fields, changed constraints), this function will not reflect the change. The full schema validation in `evaluation_control.py` is the actual backstop, but this creates a maintenance surface.

**R-4. MEDIUM — No schema constraint linking `decision` to `system_response`.**
`evaluation_control_decision.schema.json` does not enforce that `decision=require_review` pairs with `system_response=warn`, or that `decision=deny` pairs with `system_response in (freeze, block)`. The code today emits consistent pairings, but schema enforcement is absent. The `deny_budget_exhausted` rationale code is used for both `(exhausted, freeze)` and `(blocked, block)` outcomes, losing precision in the rationale.

**R-5. LOW — `deny_budget_invalid` code path is not exercised via the golden path.**
`agent_golden_path.py:_build_replay_result_for_control` synthesizes budget states "healthy", "warning", and "exhausted" but never "invalid". The `deny_budget_invalid` control path is therefore only reachable in chaos scenarios (if the fixture includes it) and not through the end-to-end golden path. A regression in the invalid handling code would not be caught by golden-path tests.

---

## 8. Recommendations

**REC-1 (Critical — fixes R-1):** Fix the budget warning override to not downgrade deny decisions.
The `warning` branch in `_apply_budget_status_override` must apply the budget warning annotation (append `budget_warning` to signals) but preserve any pre-computed `deny` decision and rationale code. The `require_review` escalation should only apply when the prior computation did not already result in `deny`. Concretely:
- If prior `decision_label == "deny"`: append `budget_warning` signal, but return the original `system_status`, `system_response`, `decision_label`, and `rationale_code` unchanged (or optionally escalate from freeze to block if desired).
- If prior `decision_label != "deny"` (i.e., allow or require_review): escalate to `require_review` as currently coded.
- Add a test asserting that `trust_breach + budget_warning → deny`, not `require_review`.

**REC-2 (High — fixes R-2):** Add the inverse `highest_severity < budget_status` check.
In `_validate_replay_budget_inputs`, add: if `_ERROR_BUDGET_SEVERITY_ORDER[budget_status] > _ERROR_BUDGET_SEVERITY_ORDER[highest_severity]`, raise `ControlLoopError("inconsistent: budget_status is more severe than highest_severity")`. This closes the one-directional validation gap.

**REC-3 (High — fixes G-1, G-2):** Add budget-state-specific tests to both chaos suite and CI gate.
- In `test_control_loop_chaos.py`: add parametrized cases that patch `error_budget_status.budget_status` (and `highest_severity`, `triggered_conditions`) directly and assert the expected `decision` and `rationale_code`.
- Extend `align_replay_budget_with_observability` or create a companion `recalculate_budget_status` helper that also updates `budget_status`, `highest_severity`, and `triggered_conditions` from objective states. Use this in the chaos precedence tests.
- In `test_eval_ci_gate.py`: add at least three tests: (a) `budget_status="warning"` on an otherwise healthy replay_result → `require_review`; (b) `budget_status="exhausted"` → gate blocks with `control_decision_blocked` reason; (c) `budget_status="invalid"` → gate blocks.

**REC-4 (Medium — fixes R-3):** Replace the partial validation in `control_loop.py` with full schema delegation.
`_validate_replay_budget_inputs` should call `_validate(budget, load_schema("error_budget_status"))` and raise on errors, then layer the cross-field consistency checks (highest_severity vs budget_status, healthy + triggered_conditions) on top. The partial structural check should not duplicate schema field names.

**REC-5 (Medium — fixes R-4):** Add schema `allOf` constraints for decision/system_response coherence.
Add a constraint that `decision=deny` requires `system_response in (freeze, block)`, and `decision=require_review` requires `system_response=warn`. Add distinct rationale codes for `deny_budget_exhausted_freeze` vs `deny_budget_exhausted_block` if the distinction is operationally meaningful.

**REC-6 (Low — fixes R-5):** Exercise `deny_budget_invalid` path in `agent_golden_path.py` tests.
Add an `AgentGoldenPathConfig` flag `force_budget_invalid=True` that sets `error_budget_status.budget_status="invalid"` in the constructed replay_result. Add a golden-path test that asserts `deny_budget_invalid` rationale is emitted.

---

## 9. Priority Classification

| ID | Recommendation | Priority | Rationale |
|---|---|---|---|
| REC-1 | Fix budget warning downgrade of deny | **Critical** | Active fail-open: deny can become require_review, enabling human override of what should be a hard governance block |
| REC-2 | Add inverse highest_severity check | **High** | Partially validated invariant; synthetic budget exhaustion cannot be detected |
| REC-3 | Add budget-state tests to chaos suite and CI gate | **High** | Budget-aware decision paths have no direct test coverage; regressions are invisible |
| REC-4 | Replace partial validation with full schema call | **Medium** | Maintenance drift risk; not currently failing, but will diverge as schema evolves |
| REC-5 | Schema constraints for decision/response coherence | **Medium** | Encoding correctness guarantee; current correct behaviour is not schema-enforced |
| REC-6 | Exercise budget_invalid path in golden path | **Low** | Coverage gap for a defined and important state; low risk of silent failure given schema validation |

---

## 10. Extracted Action Items

**BCL-CR-1** (Critical): Fix `_apply_budget_status_override` to not downgrade deny decisions on budget warning.
- Owner: Implementation engineer
- Target artifact: `spectrum_systems/modules/runtime/evaluation_control.py`
- Acceptance criteria: `trust_breach + budget_status=warning` → `decision=deny`, not `require_review`. `stability_breach + budget_status=warning` → `decision=deny`, not `require_review`. `budget_warning` signal still appended. New test confirms each case. All existing tests pass.
- Repo: Implementation repo consuming this module

**BCL-CR-2** (Critical): Add test suite for budget-aware decision paths in chaos and CI gate.
- Owner: Implementation engineer
- Target artifacts: `tests/test_control_loop_chaos.py`, `tests/test_eval_ci_gate.py`, `tests/helpers/replay_result_builder.py`
- Acceptance criteria: At minimum six new test cases covering (a) warn override of healthy-eval, (b) warn does NOT override deny-eval, (c) exhausted → deny in gate, (d) invalid → deny in gate, (e) chaos-suite parametrize for budget_status=warning/exhausted/invalid decision outcomes. `align_replay_budget_with_observability` or companion recalculates `budget_status`.
- Repo: Implementation repo

**BCL-HI-1** (High): Add inverse `highest_severity ≤ budget_status` validation to `_validate_replay_budget_inputs`.
- Owner: Implementation engineer
- Target artifact: `spectrum_systems/modules/runtime/control_loop.py`
- Acceptance criteria: `budget_status=exhausted` with `highest_severity=healthy` raises `ControlLoopError`. Existing valid artifacts continue to pass. Test added.
- Repo: Implementation repo

**BCL-HI-2** (High): Replace partial `error_budget_status` structural check in `control_loop.py` with schema delegation.
- Owner: Implementation engineer
- Target artifact: `spectrum_systems/modules/runtime/control_loop.py`
- Acceptance criteria: `_validate_replay_budget_inputs` calls `_validate(budget, load_schema("error_budget_status"))` and raises on errors. Cross-field checks (highest_severity, healthy+triggered_conditions) remain as layered guards. No duplicate field-name constants.
- Repo: Implementation repo

**BCL-MI-1** (Medium): Add schema `allOf` constraints for `decision` / `system_response` pairing.
- Owner: Schema owner
- Target artifact: `contracts/schemas/evaluation_control_decision.schema.json`
- Acceptance criteria: Schema enforces `decision=deny → system_response in (freeze, block)` and `decision=require_review → system_response=warn`. Existing emitted decisions all validate. Optionally split `deny_budget_exhausted` into `deny_budget_exhausted_freeze` and `deny_budget_exhausted_block`.
- Repo: spectrum-systems (governance)

**BCL-LI-1** (Low): Add `budget_invalid` path to `agent_golden_path.py` and golden-path test.
- Owner: Implementation engineer
- Target artifacts: `spectrum_systems/modules/runtime/agent_golden_path.py`, golden-path test file
- Acceptance criteria: Golden path with `budget_status=invalid` produces `deny_budget_invalid` decision. Test asserts rationale code.
- Repo: Implementation repo

---

## 11. Blocking Items

- **BCL-CR-1** blocks any downstream roadmap step that relies on the current `warning` budget state triggering a controlled governance response. Until fixed, a `warning` budget silently downgrades `deny` decisions, making the governance model untrustworthy for budget-warning conditions.
- No other items block forward progress, provided BCL-CR-1 is resolved.

---

## 12. Deferred Items

- **Schema rationale code precision (REC-5 / BCL-MI-1)**: Splitting `deny_budget_exhausted` into freeze vs block variants adds schema complexity. Defer until the operational distinction between freeze and block outcomes is confirmed as meaningful in the downstream enforcement model.
- **`budget_invalid` golden path coverage (BCL-LI-1)**: Low risk; defer until after critical and high items are resolved.

---

## Verdict

**PASS WITH FINDINGS.**

The budget-aware control slice is structurally sound and establishes `error_budget_status` as a genuine runtime contract input. The multi-layer validation, trace linkage enforcement, and exhausted/invalid fail-closed behavior are correct. One critical semantic defect exists: the budget warning override can downgrade a deny to require_review, which is a fail-open governance condition. This must be fixed before this slice is relied upon for budget-aware governance in production-grade gating.

**Safe to build on?** Yes, with the following condition: BCL-CR-1 must be resolved and BCL-CR-2 must provide direct test coverage of budget-state decision paths before any downstream roadmap step assumes budget warning triggers correct governance escalation.
