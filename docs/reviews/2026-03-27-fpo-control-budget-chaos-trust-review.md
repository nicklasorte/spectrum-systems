# FPO — Control / Budget / Chaos Trust-Boundary Review

---

## 1. Review Metadata

| Field | Value |
|---|---|
| Review Date | 2026-03-27 |
| Review ID | FPO-CTRL-BUDGET-CHAOS-2026-03-27 |
| Repository | nicklasorte/spectrum-systems |
| Branch | claude/fpo-control-budget-chaos-review-2OBhE |
| Reviewer / Agent | Claude (reasoning agent — Sonnet 4.6) |
| Review Standard | `docs/design-review-standard.md` |
| Review Type | FPO — surgical trust-boundary / failure-mode review |
| Action Tracker | `docs/review-actions/2026-03-27-fpo-control-budget-chaos-trust-review-actions.md` |

**Files reviewed (exact scope):**

- `spectrum_systems/modules/runtime/control_loop.py`
- `spectrum_systems/modules/runtime/evaluation_control.py`
- `spectrum_systems/modules/runtime/control_integration.py`
- `spectrum_systems/modules/runtime/agent_golden_path.py` (control/enforcement section)
- `spectrum_systems/modules/runtime/control_loop_chaos.py`
- `scripts/run_eval_ci_gate.py`
- `tests/test_control_loop_chaos.py`
- `tests/test_eval_ci_gate.py`
- `tests/helpers/replay_result_builder.py`
- `tests/fixtures/control_loop_chaos_scenarios.json`
- `contracts/schemas/evaluation_control_decision.schema.json`
- `contracts/schemas/error_budget_status.schema.json`
- `contracts/schemas/replay_result.schema.json`

---

## 2. Scope

**In-bounds:** Fail-closed semantics; budget-warning downgrade risk; replay observability metric / error_budget_status cross-enforcement; fixture and test masking of trust-boundary defects; chaos expectation strength; CI gate exit-code semantics; dead schema vocabulary and unreachable rationale codes; decision/response separation (require_review / deny / freeze / block).

**Out-of-bounds:** Modules, schemas, and test files not listed above; broad refactors; unrelated infrastructure; any path not transitively touched by the listed files.

---

## 3. Executive Summary

**Overall Verdict: CONDITIONAL PASS**

The fail-closed fundamentals across the trust boundary are intact. Every exception path in `control_loop.py` and `evaluation_control.py` produces an error, never a silent `allow`. Schema validation is applied at every artifact boundary. Trace linkage is triple-bound (`trace_id`, `replay_id`, `replay_run_id`). No change in this slice weakens the hard deny path for `trust_breach`, `stability_breach`, `budget_exhausted`, or `budget_invalid`.

However, two findings block safe merge and two more degrade the reliability of the test safety net:

- **H-01 (blocks merge):** `run_eval_ci_gate.py` does not block on `require_review` decisions by default. The CI gate uses `system_response` for its blocking check (default: `["freeze", "block"]`), omitting `"warn"`. The integration layer (`control_integration.py`) always blocks `require_review` with `continuation_allowed=False`. This semantic divergence means a `require_review` / `warn` decision exits the gate with code 0 and `status="pass"`.

- **C-01 (blocks merge):** `threshold-001` in `control_loop_chaos_scenarios.json` has an inverted description: "Pass rate exactly at threshold remains allow." The actual expected result is `status: exhausted`, `response: freeze`, `decision: deny` — driven by an exhausted error budget. This label-versus-expectation inversion will corrupt any future scenario authored to test the "threshold boundary → allow" path; contributors will use threshold-001 as a template and unknowingly set exhausted budgets.

- **H-02 (pre-merge or immediate follow-up):** No chaos scenario tests the `budget_warning + preexisting_deny` guard in `_apply_budget_status_override`. Lines 184–185 of `evaluation_control.py` are the critical semantic guarantee that budget warnings cannot downgrade an existing deny decision. That logic has no fixture-level coverage.

- **M-01:** The `only_threshold_failures → status="fail"` path in `run_eval_ci_gate.py` (lines 398–401) is unreachable in practice because threshold failures always co-trigger a control decision block via the same threshold values. No test covers this path independently. It is live code that produces a semantically distinct status token (`"fail"`) never exercised by the test suite.

---

## 4. Maturity Assessment

The control-loop trust boundary is production-grade for the hard-deny path and the budget-exhausted/invalid path. The `require_review` path diverges between the integration layer and the CI gate. Chaos fixture coverage has two structural gaps (budget_warning preservation, mislabeled threshold boundary). The fixture builder is well-aligned to the schema. Overall: **structurally sound with two trust-boundary gaps requiring immediate resolution**.

---

## 5. Strengths

- **Fail-closed on all exception paths.** `_evaluate_once` in `control_loop_chaos.py` and `run_control_loop` in `control_loop.py` both raise typed errors on every malformed-input path; the chaos runner translates errors to `{blocked/block/deny}` rather than swallowing them.
- **Layered observability-budget cross-validation.** `_validate_replay_budget_inputs` checks metric-vs-objective consistency (within 1e-6), budget_status vs highest_severity equality, and that healthy budgets have no triggered_conditions. `_to_eval_summary_from_replay_result` independently validates trace linkage and artifact-id cross-reference. These two layers are complementary, not redundant.
- **Budget-warning cannot downgrade a deny.** `_apply_budget_status_override` (lines 176–186) correctly guards the warning branch with `preexisting_deny`, which fires on `decision_label == "deny"` OR `system_response in {"block", "freeze"}`. This covers all deny surfaces.
- **Schema-validated output at every seam.** `evaluation_control_decision`, `control_trace`, and the chaos summary are all validated against JSON Schema Draft 2020-12 before returning. Invalid output raises; it does not silently pass.
- **`align_replay_budget_with_observability` is invoked on every builder path.** `make_canonical_replay_result` calls the function before and after override application, preventing silently inconsistent test fixtures.
- **All schema rationale codes are reachable.** Every rationale code declared in `evaluation_control_decision.schema.json` (`allow_healthy_eval_summary`, `deny_reliability_breach`, `deny_stability_breach`, `deny_trust_breach`, `require_review_warning_signal`, `require_review_budget_warning`, `deny_budget_exhausted`, `deny_budget_invalid`) maps to a reachable code path in `evaluation_control.py`. No dead schema vocabulary.

---

## 6. Structural Gaps

### SG-1 — CI gate `require_review` non-blocking divergence

`run_eval_ci_gate.py` line 259:
```python
if control_decision.get("system_response") in set(policy.get("blocking_system_responses", ["freeze", "block"])):
```
Default `blocking_system_responses` excludes `"warn"`. A `require_review` / `system_response="warn"` decision exits the gate with code 0 (`_EXIT_PASS`) and `status="pass"`.

`control_integration.py` line 113–116:
```python
elif final_status == "require_review":
    blocked = True
    review_required = True
    execution_status = "blocked"
```
The integration layer always blocks `require_review`. There is no analogous treatment in the CI gate.

This means the CI gate has a weaker enforcement contract than the runtime integration layer for the same class of decision. A `require_review` verdict from the control loop can merge CI green without any human review gate firing at the pipeline level.

### SG-2 — `threshold-001` description is semantically inverted

`tests/fixtures/control_loop_chaos_scenarios.json` scenario `threshold-001`:

```json
"description": "Pass rate exactly at threshold remains allow.",
"expected_status": "exhausted",
"expected_response": "freeze",
"expected_decision": "deny"
```

The description declares "remains allow" but the expected results are `freeze`/`deny`. The scenario tests budget exhaustion overriding a clean threshold boundary, not a threshold permit. No chaos test validates that the scenario description matches the expected_decision. Contributors who model future threshold-boundary tests on this scenario will inherit the mislabeled description and potentially invert their own expectations.

### SG-3 — No chaos coverage for `budget_warning + preexisting_deny` preservation

`_apply_budget_status_override` (evaluation_control.py, lines 181–185):
```python
if budget_status == "warning":
    if "budget_warning" not in triggered_signals:
        triggered_signals.append("budget_warning")
    if preexisting_deny:
        return system_status, system_response, decision_label, rationale_code
    return "warning", "warn", "require_review", "require_review_budget_warning"
```

The `preexisting_deny` guard is the only thing preventing a budget_warning from silently downgrading a `deny_reliability_breach`, `deny_stability_breach`, or `deny_trust_breach` to `require_review`. No chaos scenario exercises this guard. All budget-related scenarios in the fixture use `budget_status: "exhausted"` or `budget_status: "invalid"`.

---

## 7. Risk Areas

### R-1 — Metric-objective cross-validation is conditional on objectives being present

`_validate_replay_budget_inputs` (control_loop.py, lines 120–129):
```python
for metric_name in ("replay_success_rate", "drift_exceed_threshold_rate"):
    metric_value = metrics.get(metric_name)
    objective = objective_by_metric.get(metric_name)
    if isinstance(metric_value, (int, float)) and isinstance(objective, dict):
        ...
```
The consistency check fires only when **both** the metric and the matching objective exist. A `replay_result` with an empty or sparse `objectives` array passes all metric-consistency checks regardless of metric values. The chaos fixture always provides both objectives, so this gap is not currently exploited, but it represents a silent validation skip if future fixtures omit objectives for either tracked metric.

### R-2 — `only_threshold_failures → status="fail"` is unreachable through the test suite

`run_eval_ci_gate.py` lines 395–404:
```python
threshold_failed = any(reason.startswith("threshold_failed:") for reason in blocking_reasons)
only_threshold_failures = threshold_failed and all(
    reason.startswith("threshold_failed:") for reason in blocking_reasons
)
if only_threshold_failures:
    status = "fail"
    exit_code = _EXIT_FAIL
else:
    status = "blocked"
    exit_code = _EXIT_FAIL
```

In practice, threshold violations trigger a matching control decision block (same thresholds → same verdict). The `only_threshold_failures` branch therefore never fires without a co-occurring `control_decision_blocked:` reason; `status="fail"` is never produced by the test suite. `test_threshold_failure_fails_closed` expects `status="blocked"` precisely because the control loop also blocks. This path produces a distinct status token (`"fail"`) consumed by downstream observability, but it is dead from a test coverage perspective.

### R-3 — `indeterminate_failure` alone (no trust_breach) yields `require_review`, not `deny`

`evaluation_control.py` lines 233–244: `indeterminate_failure` is a `SEVERE_SIGNAL`. With one severe hit, and no trust_breach, and no second severe signal, `system_status = "warning"`. This yields `decision = "require_review"` / `system_response = "warn"`.

With default thresholds (`trust_threshold = 0.80`), `consistency_status = "indeterminate"` maps to `reproducibility_score = 0.5`, which is below 0.80 → `trust_breach` fires anyway. So the pure `indeterminate_failure` path is unreachable at default thresholds.

However: if a policy sets `trust_threshold < 0.5`, `indeterminate` consistency would yield only `indeterminate_failure` (no trust_breach), and the decision would be `require_review`/`warn`. Combined with SG-1 (CI gate non-blocking `warn`), this would produce a gate exit code 0 for an indeterminate replay result. No chaos scenario tests the `indeterminate_failure`-only boundary.

### R-4 — `align_replay_budget_state` does not update individual objective statuses when `budget_status="invalid"`

`replay_result_builder.py` lines 137–141:
```python
if budget_status == "invalid":
    budget["budget_status"] = "invalid"
    budget["highest_severity"] = "invalid"
    budget["triggered_conditions"] = []
    budget["reasons"] = []
```
Individual `objectives[].status` fields are not updated. After this call, a fixture may show `budget_status="invalid"` with each objective still showing `status="healthy"`. The schema and `_validate_replay_budget_inputs` do not check individual objective status against the aggregate budget_status, so this inconsistency passes all validation. It does not cause a semantic defect but creates misleading fixture state.

---

## 8. Recommendations

1. **Add `"warn"` to `blocking_system_responses` in the default policy, or change the gate to block on `decision == "require_review"` regardless of system_response.** Either approach aligns the CI gate with the enforcement layer. Changing the gate to check `decision` directly is the stronger fix because it is independent of policy configuration.

2. **Correct `threshold-001` description to accurately describe what the scenario tests.** Replace "Pass rate exactly at threshold remains allow." with a description that captures the budget-exhausted override semantics, e.g.: "Pass rate and drift rate at exact threshold boundaries — budget exhaustion overrides to freeze/deny."

3. **Add a chaos scenario for `budget_warning + preexisting_deny`.** The scenario should supply a replay_result with `budget_status: "warning"` and metrics below `reliability_threshold` (triggering `reliability_breach → deny`). Expected: original deny/freeze is preserved; `budget_warning` is added to `triggered_signals` but does not change `decision`.

4. **Add a chaos scenario for `budget_warning + no_preexisting_deny`** (healthy signals, warning budget). Expected: `require_review` / `warn` / `require_review_budget_warning`. This validates the non-preexisting_deny branch.

5. **Consider adding a test that reaches `status="fail"` in the CI gate** by supplying a policy whose `blocking_system_responses` excludes `"freeze"` but whose thresholds still fail. This would verify the `fail` status token is produced correctly and is distinct from `blocked`.

6. **Document the `budget_exhausted + stability_breach` behavior** in the chaos fixture. Currently no scenario tests that `stability_breach` alone (no trust_breach, no indeterminate_failure) with `budget_exhausted` yields `exhausted/freeze` rather than `blocked/block`. This is a deliberate design choice but is not coverage-verified.

---

## 9. Priority Classification

| ID | Severity | Description |
|---|---|---|
| C-01 | **Critical** | `threshold-001` description is inverted — "remains allow" vs actual `freeze/deny` — will corrupt future test authoring |
| H-01 | **High** | CI gate does not block `require_review` by default; diverges from integration layer enforcement semantics |
| H-02 | **High** | No chaos scenario covers `budget_warning + preexisting_deny` preservation (the deny-preservation guard is untested) |
| M-01 | **Medium** | `status="fail"` path (`only_threshold_failures`) is unreachable in the test suite; dead coverage |
| M-02 | **Medium** | Metric-objective cross-validation silently skips when objectives are sparse or empty |
| M-03 | **Medium** | Pure `indeterminate_failure` (no trust_breach) + low trust_threshold → gate exit 0; no scenario tests this boundary |
| L-01 | **Low** | `align_replay_budget_state` does not update individual objective statuses for `budget_status="invalid"`; misleading fixture state |
| L-02 | **Low** | `budget_exhausted + stability_breach` (no trust_breach) yields `freeze` not `block`; undocumented and uncovered by fixture |

---

## 10. Extracted Action Items

| ID | Finding | Action | Target |
|---|---|---|---|
| FPO-CA-01 | C-01 | Correct `threshold-001` scenario description in chaos fixture | `tests/fixtures/control_loop_chaos_scenarios.json` |
| FPO-CA-02 | H-01 | Change CI gate to block on `decision == "require_review"` OR add `"warn"` to default `blocking_system_responses` | `scripts/run_eval_ci_gate.py` |
| FPO-CA-03 | H-02 | Add chaos scenario: `budget_warning + reliability_breach → deny preserved` | `tests/fixtures/control_loop_chaos_scenarios.json` |
| FPO-CA-04 | H-02 | Add chaos scenario: `budget_warning + healthy_signals → require_review` | `tests/fixtures/control_loop_chaos_scenarios.json` |
| FPO-CA-05 | M-01 | Add test covering pure threshold-failure path without control decision block | `tests/test_eval_ci_gate.py` |
| FPO-CA-06 | M-02 | Add validation check: warn when key objectives are absent from `objectives` array | `spectrum_systems/modules/runtime/control_loop.py` |
| FPO-CA-07 | M-03 | Add chaos scenario: `indeterminate_failure` only, `trust_threshold < 0.5`, healthy budget | `tests/fixtures/control_loop_chaos_scenarios.json` |
| FPO-CA-08 | L-01 | Update `align_replay_budget_state` to set individual objective statuses for `budget_status="invalid"` | `tests/helpers/replay_result_builder.py` |
| FPO-CA-09 | L-02 | Add chaos scenario: `stability_breach + budget_exhausted` → `freeze` (not `block`) | `tests/fixtures/control_loop_chaos_scenarios.json` |

---

## 11. Blocking Items

The following must be resolved before this branch is safe to merge:

- **FPO-CA-01**: Correct the `threshold-001` description. The description is navigable by contributors as a canonical example of threshold-boundary behavior. The current mislabeled description ("remains allow") will directly mislead future test authors.
- **FPO-CA-02**: Align CI gate `require_review` blocking with the integration layer. As documented in SG-1, a `require_review` control decision currently exits the gate with code 0. This diverges from the enforcement contract and silently permits execution on require_review verdicts.

---

## 12. Deferred Items

- **FPO-CA-05** through **FPO-CA-09**: Coverage improvements that strengthen the test safety net but do not constitute an immediate trust-boundary regression. Recommended before next iteration but not blocking.
- **R-3 / FPO-CA-07**: The `indeterminate_failure` alone + low trust_threshold scenario is theoretical at current default thresholds. Deferred unless policy flexibility for `trust_threshold` below 0.5 is introduced.

---

## 13. Follow-up Triggers

| Trigger | Action |
|---|---|
| FPO-CA-01 and FPO-CA-02 merged | Re-run chaos suite and CI gate tests to confirm no regression |
| Any change to `blocking_system_responses` default or `_apply_budget_status_override` | Re-run this review scope |
| `trust_threshold` made policy-configurable below 0.5 | Escalate R-3 / FPO-CA-07 from deferred to required |
| Any new budget path added to `evaluation_control.py` | Chaos fixture must receive a corresponding scenario before merge |
