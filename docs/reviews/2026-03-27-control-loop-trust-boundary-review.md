# Control Loop Trust Boundary Review

---

## 1. Review Metadata

| Field | Value |
|---|---|
| Review Date | 2026-03-27 |
| Repository | nicklasorte/spectrum-systems |
| Branch | claude/review-control-loop-trust-boundary-review |
| Reviewer / Agent | Claude (reasoning agent) |
| Review Standard | `docs/design-review-standard.md` |
| Action Tracker | `docs/review-actions/2026-03-27-control-loop-trust-boundary-review-actions.md` |

**Inputs consulted:**
- `spectrum_systems/modules/runtime/control_loop.py`
- `spectrum_systems/modules/runtime/control_integration.py`
- `spectrum_systems/modules/runtime/agent_golden_path.py` (control/enforcement section)
- `spectrum_systems/modules/runtime/control_loop_chaos.py`
- `spectrum_systems/modules/runtime/evaluation_control.py`
- `spectrum_systems/modules/runtime/enforcement_engine.py`
- `contracts/schemas/replay_result.schema.json`
- `contracts/schemas/evaluation_control_decision.schema.json`
- `contracts/schemas/enforcement_result.schema.json`

---

## 2. Scope

**In-bounds:**
- `replay_result` → `control_loop` → `enforcement_engine` execution path
- Trace context construction and binding: `trace_id`, `replay_id`, `replay_run_id`
- Signal normalization and validation in `_normalize_signal` / `_validate_normalized_signal`
- Observability ↔ error budget linkage checks in `evaluation_control.py`
- Fail-closed semantics across all failure paths
- Precedence and decision logic in `build_evaluation_control_decision`
- Chaos test alignment in `control_loop_chaos.py`
- Integration gate behavior in `enforce_control_before_execution`

**Out-of-bounds:**
- `control_executor.py`, `contract_runtime.py`, `evaluation_auto_generation.py`
- All modules not listed in the scope statement
- Schemas not directly consumed by in-scope modules

---

## 3. Executive Summary

**Overall Verdict: CONDITIONAL PASS**

The control loop trust boundary is structurally sound: it is fail-closed at all critical decision points, schema-validated at every artifact boundary, and trace-bound through strict equality checks. No path exists to bypass the enforcement gate or produce an `allow` decision from a malformed input.

However, four issues compromise diagnostic integrity and testability:

- The `deny_indeterminate_failure` rationale code is unreachable by construction, creating dead schema vocabulary and misleading downstream consumers.
- `enforce_control_before_execution` breaks its own "always return integration_result" contract by raising an exception (instead of returning a blocked result) when `EvalCaseGenerationError` occurs on a blocked path.
- `_normalize_signal` builds a `decision_inputs` dict that is never consumed downstream — this is dead logic that provides false pre-validation confidence.
- The chaos test has a silent `expected_decision` default of `"deny"` that misclassifies `require_review` outcomes in scenarios that omit the field.

None of these constitute a security bypass, but two (the exception-escape path and the dead rationale code) are concrete failure modes for observability and operator diagnosis.

---

## 4. Maturity Assessment

The replay → control → enforcement path is production-grade for the happy path and the strict-deny path. The `require_review` path has a semantic inconsistency at the integration layer. Chaos test coverage has gaps in the `indeterminate` and `require_review` branches. Overall: **functionally mature with diagnostic gaps**.

---

## 5. Strengths

- **Fail-closed by default across all exception paths.** Every unhandled signal type, schema violation, and trace mismatch produces a `ControlLoopError` or `EnforcementError`, never a silent `allow`.
- **Triple trace binding.** `_validate_trace_context_binding` enforces exact equality of `trace_id`, `replay_id`, and `replay_run_id` between trace_context and artifact before evaluation proceeds.
- **Schema-validated output at every boundary.** `evaluation_control_decision`, `enforcement_result`, and `control_trace` are all validated against JSON Schema Draft 2020-12 before returning. Invalid output raises, not passes.
- **Deterministic decision ID.** Both `evaluation_control_decision.decision_id` and `enforcement_result.enforcement_result_id` are derived via SHA-256 from their identity payload — replay produces the same IDs.
- **Adapter pattern isolates control gate.** `run_simulation_with_control` and `generate_working_paper_with_control` cannot call their payload functions unless `continuation_allowed` is True — the gate cannot be partially bypassed by the caller.
- **Legacy enforcement path is caller-restricted.** `enforce_budget_decision` uses stack inspection and raises on unauthorized callers.

---

## 6. Structural Gaps

### G1 — Dead rationale code: `deny_indeterminate_failure` is unreachable

`evaluation_control.py` hardcodes `reproducibility_score = 0.5` for `consistency_status = "indeterminate"`. With default `trust_threshold = 0.80`, this always triggers `trust_breach` alongside `indeterminate_failure`. In `build_evaluation_control_decision`, the elif chain checks `"trust_breach" in triggered_signals` before `"indeterminate_failure"`, so `deny_indeterminate_failure` is never reached. The rationale code is registered in the schema enum but cannot be emitted through any normal control-loop execution.

**Failure mode:** Consumers expecting `rationale_code = deny_indeterminate_failure` receive `deny_trust_breach` instead. Any downstream system routing on rationale code will route indeterminate failures incorrectly.

---

### G2 — `enforce_control_before_execution` exception escape on blocked path

In `control_integration.py` lines 325–345: when execution is blocked and `generate_failure_eval_case` raises `EvalCaseGenerationError`, the function re-raises as `ContractRuntimeError` instead of returning the already-constructed `integration_result`. This breaks three invariants:

1. The function does not always return an integration_result dict (documented contract).
2. The `_log_integration_outcome` call at line 348 is never reached — the block is not observable.
3. The adapter pattern (`run_simulation_with_control`) cannot inspect the partial result; it receives an unhandled exception instead.

**Failure mode:** A secondary failure in eval case generation on a legitimately-blocked execution produces an opaque exception instead of a structured, observable blocked result. Callers have no way to distinguish this from a control-loop failure.

---

### G3 — `_normalize_signal` produces dead `decision_inputs` dict

`control_loop.py` lines 35–39: `_normalize_signal` builds `decision_inputs = {consistency_status, has_observability_metrics, has_error_budget_status}`. `_evaluate_signal` ignores the normalized signal entirely and passes the raw `artifact` to `build_evaluation_control_decision`. The `decision_inputs` dict is constructed but never consumed.

**Failure mode:** Callers of `_normalize_signal` cannot rely on `decision_inputs` to determine pre-validation status, as it has no effect on the actual evaluation. This creates a false impression that presence of `observability_metrics` and `error_budget_status` is checked before evaluation when in fact it is not — the check happens later inside `build_evaluation_control_decision`.

---

### G4 — `consistency_status = "indeterminate"` is never constructed by the golden path

`agent_golden_path.py` `_build_replay_result_for_control` (lines 197–199) produces only `"match"` or `"mismatch"` based on `reproducibility < 0.8`. The `"indeterminate"` branch in the schema and the `indeterminate_failure` signal path are unreachable through the golden path fixture. The chaos test cannot exercise this path without raw artifact construction.

**Failure mode:** The indeterminate consistency path has no golden path regression coverage. Behavioral regressions in the `indeterminate_failure` signal chain would not be caught by standard golden path runs.

---

## 7. Risk Areas

### R1 — `require_review` enforcement state: `publication_blocked = False`, `decision_blocked = False`

In `control_integration.py` lines 113–117, the `require_review` enforcement result maps to `blocked=False`, meaning `publication_blocked = False` and `decision_blocked = False`, while `execution_status = "blocked"` and `continuation_allowed = False`. This is semantically asymmetric: execution is blocked, but the publication and decision flags suggest the artifact could be used downstream.

**Risk:** A consumer reading only `publication_blocked` or `decision_blocked` could incorrectly proceed with an artifact that is pending human review. The distinction from `deny` (where these flags are `True`) is subtle and requires callers to read all three fields.

---

### R2 — Chaos test silent `expected_decision` default of `"deny"`

`control_loop_chaos.py` line 133: scenarios that omit `expected_decision` default to `"deny"`. `require_review` outcomes from the control loop would fail such scenarios even if `expected_status` and `expected_response` match correctly. Conversely, a scenario written to test `require_review` that forgets `expected_decision` will pass only if the system returns `"deny"` — the wrong outcome.

**Risk:** Chaos scenarios testing the `require_review` path are silently incorrect unless `expected_decision` is explicitly set to `"require_review"`. This creates false-positive failures or false-negative passes depending on scenario intent.

---

### R3 — Chaos test `_is_match` reason check is subset-only

`control_loop_chaos.py` line 148: `_is_match` checks that all expected reasons are present in actual reasons (`expected ⊆ actual`), but does not check that no unexpected reasons are present. An adversarial or regressed implementation emitting extra signal codes does not fail the match.

**Risk:** Signal pollution (unexpected rationale or trigger codes) is invisible to the chaos test. A regressed implementation emitting `trust_breach` in addition to `reliability_breach` on a healthy artifact would not be caught if only `reliability_breach` was listed as `expected_reasons`.

---

### R4 — Chaos `_evaluate_once` does not catch `AttributeError` or unexpected exceptions

`control_loop_chaos.py` lines 112–120: exception handling covers `(ControlLoopError, EvaluationControlError, ValueError, TypeError, KeyError)` but excludes `AttributeError` and other exception types. A malformed artifact that triggers an `AttributeError` in the control loop would propagate as an unhandled exception from `_evaluate_once`, not as a bounded `"blocked/deny"` result.

**Risk:** Chaos scenarios with sufficiently malformed artifacts can cause the chaos runner to fail with an unhandled exception rather than producing a structured mismatch result.

---

### R5 — `"freeze"` system_response collapses to `"deny"` without distinct enforcement state

`evaluation_control.py`: `system_status = "exhausted"` → `system_response = "freeze"`. In `build_evaluation_control_decision`, both `"freeze"` and `"block"` system responses produce `decision_label = "deny"`. The `enforcement_result` cannot distinguish between an `"exhausted"` (budget depleted) outcome and a `"blocked"` (trust violated) outcome. The `rationale_code` differentiates them (`deny_stability_breach` vs `deny_trust_breach`), but the enforcement action is identical.

**Risk:** Systems routing on `enforcement_action` or `final_status` alone cannot distinguish budget exhaustion from trust failure — two operationally distinct conditions that may warrant different remediation paths.

---

## 8. Recommendations

### REC-01 (Critical → G1, R2) — Align `indeterminate` reproducibility mapping or remove dead rationale code

Either:
- (a) Adjust the `reproducibility_score` mapping for `"indeterminate"` to a value at or above `trust_threshold` (e.g., 0.9) so `trust_breach` is not always co-triggered, making `deny_indeterminate_failure` reachable; or
- (b) Remove `deny_indeterminate_failure` from the schema enum, rationale code mapping, and elif chain, and document that indeterminate consistency always routes through `deny_trust_breach`.

Option (b) is safer in the near term: it removes dead vocabulary and makes the actual routing explicit.

**Expected outcome:** Schema enum, implementation, and test expectations are consistent. No dead rationale code.

---

### REC-02 (High → G2) — Return blocked integration_result on `EvalCaseGenerationError`, do not raise

In `control_integration.py` lines 325–345: catch `EvalCaseGenerationError`, attach the error detail to `integration_result["generated_failure_eval_case_error"]`, and fall through to the observability log and return. The function must always return a structured result.

**Expected outcome:** Secondary eval-case-generation failures on blocked paths are observable (logged), callers always receive a dict, and the blocked execution is still correctly reported.

---

### REC-03 (High → G3) — Remove `decision_inputs` from `_normalize_signal` or connect it to gating

Either:
- (a) Remove `decision_inputs` from the normalized signal entirely (it is never consumed); or
- (b) Promote `has_observability_metrics` and `has_error_budget_status` to pre-validation gates that raise `ControlLoopError` before calling `_evaluate_signal`.

Option (b) would make the signal normalization layer load-bearing rather than decorative.

**Expected outcome:** The `_normalize_signal` contract matches its actual behavior; no false pre-validation confidence.

---

### REC-04 (High → R1) — Align `require_review` `publication_blocked` / `decision_blocked` semantics

In `control_integration.py`: for `require_review`, set `publication_blocked = True` and `decision_blocked = True` (matching `deny`), but keep `human_review_required = True` and `escalation_triggered = False`. If the intent is that `require_review` allows publication after review, document this explicitly and add a caller assertion that callers must check `human_review_required` before treating these as usable.

**Expected outcome:** Callers cannot misread `publication_blocked = False` as permission to publish a `require_review`-gated artifact.

---

### REC-05 (Medium → R2) — Add `expected_decision` to chaos scenario schema validation

In `control_loop_chaos.py` `_validate_scenario_shape`: add `expected_decision` to the required fields list, or validate that its value is one of the known decision labels. Remove the silent default of `"deny"` from `_build_expectation`.

**Expected outcome:** Scenarios omitting `expected_decision` fail at load time rather than silently defaulting. Require_review scenarios are correctly specified.

---

### REC-06 (Medium → G4) — Add an indeterminate fixture to the golden path or chaos scenario corpus

Add at least one chaos scenario with a raw `replay_result` artifact where `consistency_status = "indeterminate"` (with correct `failure_reason` and `drift_detected = false` per schema). This exercises the indeterminate trust_breach path end-to-end.

**Expected outcome:** The indeterminate path has regression coverage.

---

### REC-07 (Medium → R3) — Change chaos `_is_match` reason check to exact-set equality

Replace the subset check with `actual_reasons == set(expectation.expected_reasons)` to catch unexpected signal codes. Where extra reasons are intentionally acceptable, allow scenarios to specify an `allow_extra_reasons: true` flag.

**Expected outcome:** Reason set pollution triggers scenario failure.

---

### REC-08 (Low → R4) — Broaden chaos `_evaluate_once` exception handler

Add `Exception` as a final catch (or at minimum `AttributeError`) to `_evaluate_once`. The catch should return the standard blocked/deny result with `error = str(exc)` and log the unexpected exception type.

**Expected outcome:** Malformed chaos artifacts always produce a bounded result; the chaos runner does not abort on unexpected exception types.

---

## 9. Priority Classification

| # | Recommendation | Priority | Rationale |
|---|---|---|---|
| REC-01 | Remove or realign `deny_indeterminate_failure` | Critical | Dead schema vocabulary; misroutes indeterminate signals silently |
| REC-02 | Return blocked result on `EvalCaseGenerationError` | High | Breaks "always return dict" contract; makes blocked executions unobservable |
| REC-03 | Remove or connect `decision_inputs` in `_normalize_signal` | High | Dead logic with false pre-validation confidence |
| REC-04 | Align `require_review` `publication_blocked`/`decision_blocked` | High | Semantic inconsistency that permits misreading by callers |
| REC-05 | Require `expected_decision` in chaos scenarios | Medium | Silent default produces incorrect scenario expectations |
| REC-06 | Add indeterminate fixture to chaos or golden path corpus | Medium | Untestable code path; no regression coverage |
| REC-07 | Exact-set reason matching in `_is_match` | Medium | Subset check misses signal pollution |
| REC-08 | Broaden `_evaluate_once` exception handler | Low | Non-critical; chaos runner stability concern only |

---

## 10. Extracted Action Items

1. **[REC-01]** Audit `deny_indeterminate_failure` reachability and either remove it from the schema enum and elif chain, or modify the reproducibility mapping for `indeterminate` consistency_status. Acceptance: no dead rationale codes in schema enum; implementation routes are reachable. Owner: unassigned. Artifact: updated `evaluation_control.py` + `evaluation_control_decision.schema.json`.

2. **[REC-02]** Modify `enforce_control_before_execution` to catch `EvalCaseGenerationError` and return a structured blocked result instead of re-raising as `ContractRuntimeError`. Acceptance: function always returns integration_result dict; blocked path is logged. Owner: unassigned. Artifact: updated `control_integration.py`.

3. **[REC-03]** Remove `decision_inputs` from `_normalize_signal` return value, or promote its checks to pre-evaluation gates that raise `ControlLoopError`. Acceptance: signal dict contains no dead fields; any presence-check failure is explicit. Owner: unassigned. Artifact: updated `control_loop.py`.

4. **[REC-04]** Set `publication_blocked = True` and `decision_blocked = True` for `require_review` enforcement in `_execution_result_from_enforcement_result`, or add explicit caller documentation asserting that these flags require checking `human_review_required`. Acceptance: `require_review` and `deny` enforce the same publication boundary. Owner: unassigned. Artifact: updated `control_integration.py`.

5. **[REC-05]** Add `expected_decision` to the required fields in `_validate_scenario_shape` and remove the `"deny"` default from `_build_expectation`. Acceptance: scenarios without `expected_decision` raise `ControlLoopChaosError` at load time. Owner: unassigned. Artifact: updated `control_loop_chaos.py`.

6. **[REC-06]** Create at least one chaos scenario fixture with `consistency_status = "indeterminate"` and correct schema-compliant values (`failure_reason` non-null, `drift_detected = false`). Acceptance: chaos run exercises the indeterminate → trust_breach → deny path. Owner: unassigned. Artifact: new or updated chaos scenario JSON file.

7. **[REC-07]** Replace the subset reason check in `_is_match` with exact-set equality, with optional `allow_extra_reasons` override per scenario. Acceptance: scenarios fail when actual reasons differ from expected in either direction. Owner: unassigned. Artifact: updated `control_loop_chaos.py`.

8. **[REC-08]** Extend `_evaluate_once` exception handling to catch `AttributeError` (and optionally `Exception`) to prevent chaos runner abort on malformed fixtures. Acceptance: all artifact types produce a bounded blocked result. Owner: unassigned. Artifact: updated `control_loop_chaos.py`.

---

## 11. Blocking Items

- **REC-01** (dead rationale code) should be resolved before extending any downstream system that routes on `rationale_code`. The `deny_indeterminate_failure` code is in the public schema enum and its unreachability is invisible to schema consumers.
- **REC-02** (exception escape on blocked path) should be resolved before chaos runs or integration tests are used as observability evidence. Blocked paths that secondary-fail are currently unlogged.

---

## 12. Deferred Items

- Detailed audit of custom `thresholds` injection surface in `build_evaluation_control_decision` — thresholds are accepted without pre-validation; out-of-range values are only caught post-construction by schema validation. Acceptable for now given schema enforcement, but worth a dedicated review if threshold injection becomes a runtime-configurable surface.
- Review of the `enforce_budget_decision` legacy caller allowlist mechanism — stack-frame inspection is fragile under refactoring. Deferred to a dedicated legacy-surface review.
