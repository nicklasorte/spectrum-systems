# Action Tracker — FPO Control / Budget / Chaos Trust-Boundary Review

**Source review:** `docs/reviews/2026-03-27-fpo-control-budget-chaos-trust-review.md`
**Review ID:** FPO-CTRL-BUDGET-CHAOS-2026-03-27
**Date:** 2026-03-27
**Agent:** Claude (Sonnet 4.6)

---

## Blocking Items (must resolve before merge)

### FPO-CA-01 — Correct `threshold-001` scenario description

| Field | Value |
|---|---|
| ID | FPO-CA-01 |
| Finding | C-01 |
| Severity | Critical |
| Status | Open |
| Owner | Codex |
| Blocking | Yes — merge blocked |
| File | `tests/fixtures/control_loop_chaos_scenarios.json` |

**Current description (wrong):**
```
"Pass rate exactly at threshold remains allow."
```

**Required description (accurate):**
```
"Pass rate and drift rate at exact threshold boundaries — budget exhaustion overrides to freeze/deny."
```

**Why it blocks:** The description is a canonical example read by contributors writing threshold-boundary scenarios. The current text ("remains allow") is semantically inverted from the actual expectation (`freeze/deny`). Any future scenario modeled on this will inherit the wrong semantics.

**Codex instruction:**
In `tests/fixtures/control_loop_chaos_scenarios.json`, locate scenario `"scenario_id": "threshold-001"` and update the `"description"` field to:
```
"Pass rate and drift rate at exact threshold boundaries — budget exhaustion overrides clean threshold boundary to freeze/deny."
```
No other field in this scenario should change.

---

### FPO-CA-02 — Align CI gate `require_review` blocking with enforcement layer

| Field | Value |
|---|---|
| ID | FPO-CA-02 |
| Finding | H-01 |
| Severity | High |
| Status | Open |
| Owner | Codex |
| Blocking | Yes — merge blocked |
| File | `scripts/run_eval_ci_gate.py` |

**Current behavior:** Line 259 in `run_eval_ci_gate.py`:
```python
if control_decision.get("system_response") in set(policy.get("blocking_system_responses", ["freeze", "block"])):
```
`"warn"` is not in the default set. `require_review` decisions (`system_response="warn"`) exit the gate with code 0 and `status="pass"`.

**Enforcement layer behavior (`control_integration.py` line 113–116):** `require_review` always produces `execution_status="blocked"`, `continuation_allowed=False`.

**Required fix (preferred — check `decision` field, not `system_response`):**

Replace the blocking check with:
```python
if control_decision.get("decision") in {"deny", "require_review"}:
    blocking_reasons.append(
        f"control_decision_blocked: {control_decision.get('system_response')}"
    )
```

**Alternative fix (policy-level):** Add `"warn"` to `blocking_system_responses` default list. This is weaker because it remains policy-configurable.

**Required test update:** Add a test case to `tests/test_eval_ci_gate.py` that verifies a `require_review` control decision (low reproducibility but above trust threshold, healthy budget) produces exit code 1. The existing `test_blocking_control_decision_fails_closed` covers trust_breach → block; this new test should cover `require_review` → block independently.

**Codex instruction (preferred approach):**

In `scripts/run_eval_ci_gate.py`, replace the `control_decision.get("system_response") in set(...)` blocking check (current line 259) with a check on `control_decision.get("decision")`:
```python
control_decision_value = control_decision.get("decision")
if control_decision_value in {"deny", "require_review"}:
    blocking_reasons.append(
        f"control_decision_blocked: {control_decision.get('system_response')}"
    )
```
Then update `test_eval_ci_gate.py` to add a test that verifies `require_review` exits with code 1.

---

## High-Priority Items (pre-merge or immediate follow-up)

### FPO-CA-03 — Add chaos scenario: `budget_warning + reliability_breach → deny preserved`

| Field | Value |
|---|---|
| ID | FPO-CA-03 |
| Finding | H-02 |
| Severity | High |
| Status | Open |
| Owner | Codex |
| Blocking | Recommended pre-merge; required before next chaos fixture iteration |
| File | `tests/fixtures/control_loop_chaos_scenarios.json` |

**What to add:** A scenario with:
- `consistency_status: "match"` (no trust_breach from reproducibility)
- `replay_success_rate` below `reliability_threshold` (0.85), e.g., 0.70
- `drift_exceed_threshold_rate` at or below `drift_threshold` (0.20), e.g., 0.10
- `budget_status: "warning"` in `error_budget_status`
- Expected: `status: "warning"`, `response: "freeze"`, `decision: "deny"`, reasons include `["deny_reliability_breach", "reliability_breach", "budget_warning"]`

Wait — if `reliability_breach` triggers → `system_status = "warning"` (one non-severe signal, no stability_breach, no trust_breach) → `system_response = "warn"` → `decision = "require_review"`. Then `preexisting_deny` checks `decision_label == "deny"` which is False here, and `system_response in {"block", "freeze"}` which is also False ("warn"). So `preexisting_deny = False`. The budget warning overrides to `require_review/warn`.

**Correction:** The `preexisting_deny` guard fires when the original decision is already deny. For `reliability_breach` alone, `decision = "require_review"` (not deny). To test the `preexisting_deny` guard, we need a scenario where the pre-budget decision is `deny` — that means `stability_breach` (which produces `system_response = "freeze"`, `decision = "deny"`).

**Revised scenario:** Supply a replay_result with:
- `drift_exceed_threshold_rate` above `drift_threshold` (0.20), e.g., 0.40 (triggers `stability_breach`)
- `replay_success_rate` at/above `reliability_threshold` (0.85)
- `consistency_status: "match"` (no trust_breach)
- `budget_status: "warning"` in `error_budget_status`, properly aligned with observability metrics

Expected: `status: "exhausted"`, `response: "freeze"`, `decision: "deny"`, reasons include `["deny_stability_breach", "stability_breach", "budget_warning"]`

This validates that `budget_warning` appends `budget_warning` to triggered_signals but does NOT change the response from freeze to warn.

**Codex instruction:**
Add a new scenario with `"scenario_id": "budget-warning-001"` to `tests/fixtures/control_loop_chaos_scenarios.json` using the above parameters. The `error_budget_status` objectives must have `observed_value` fields consistent with the `observability_metrics.metrics` values (use `align_replay_budget_with_observability` semantics). The `budget_status` should be `"warning"` with `highest_severity: "warning"` and appropriate `triggered_conditions` for at least one metric.

---

### FPO-CA-04 — Add chaos scenario: `budget_warning + healthy signals → require_review`

| Field | Value |
|---|---|
| ID | FPO-CA-04 |
| Finding | H-02 |
| Severity | High |
| Status | Open |
| Owner | Codex |
| Blocking | Recommended pre-merge |
| File | `tests/fixtures/control_loop_chaos_scenarios.json` |

**What to add:** A scenario with all signal metrics above thresholds (healthy signals: `replay_success_rate ≥ 0.85`, `drift_exceed_threshold_rate ≤ 0.20`, `consistency_status: "match"`) but `budget_status: "warning"`.

Expected: `status: "warning"`, `response: "warn"`, `decision: "require_review"`, reasons include `["budget_warning", "require_review_budget_warning"]`

This tests the non-`preexisting_deny` branch of `_apply_budget_status_override` for budget_warning.

---

## Medium-Priority Items

### FPO-CA-05 — Add CI gate test for pure threshold-failure (`status="fail"`)

| Field | Value |
|---|---|
| ID | FPO-CA-05 |
| Finding | M-01 |
| Severity | Medium |
| Status | Open |
| Owner | Codex |
| Blocking | No |
| File | `tests/test_eval_ci_gate.py` |

**What to add:** A test that produces threshold failures without a co-occurring control decision block. This requires a policy where `blocking_system_responses` does NOT include the system_response produced by the control decision, OR a threshold violation that falls below the control decision's blocking threshold.

Simplest approach: Set `pass_rate_min` in policy thresholds to 0.99, but set `blocking_system_responses: []` (empty). The eval_summary would have pass_rate=1.0 (from forced_status="pass"), but if the control decision yields `warn` (reliability near-breach) and `blocking_system_responses` is empty, only threshold_failed reasons would fire.

Alternatively, test with a policy that has `pass_rate_min=0.99` but `blocking_system_responses=[]` and metrics that marginally fail threshold but produce a `require_review` that doesn't block (since the list is empty).

**Expected test assertions:**
```python
assert code == 1
assert summary["status"] == "fail"  # not "blocked"
assert all(reason.startswith("threshold_failed:") for reason in summary["blocking_reasons"])
```

---

### FPO-CA-06 — Warn or error when key objectives are absent from `objectives` array

| Field | Value |
|---|---|
| ID | FPO-CA-06 |
| Finding | M-02 |
| Severity | Medium |
| Status | Open |
| Owner | Codex |
| Blocking | No |
| File | `spectrum_systems/modules/runtime/control_loop.py` |

**What to add:** In `_validate_replay_budget_inputs`, after building `objective_by_metric`, add a check that warns (or raises) when neither `replay_success_rate` nor `drift_exceed_threshold_rate` appears in the objectives for a non-healthy budget:

```python
if budget_status != "healthy":
    missing_objectives = [
        m for m in ("replay_success_rate", "drift_exceed_threshold_rate")
        if m not in objective_by_metric
    ]
    if missing_objectives:
        raise ControlLoopError(
            f"error_budget_status is {budget_status!r} but objectives for "
            f"{missing_objectives} are absent — cross-validation cannot proceed"
        )
```

This closes the silent skip for sparse objectives arrays on non-healthy budgets.

---

### FPO-CA-07 — Add chaos scenario: `indeterminate_failure` only with low trust_threshold

| Field | Value |
|---|---|
| ID | FPO-CA-07 |
| Finding | M-03 |
| Severity | Medium |
| Status | Open |
| Owner | Codex |
| Blocking | No; deferred until trust_threshold policy range is finalized |
| File | `tests/fixtures/control_loop_chaos_scenarios.json` |

**What to add:** A scenario with `consistency_status: "indeterminate"`, healthy budget, `replay_success_rate ≥ 0.85`, `drift_exceed_threshold_rate ≤ 0.20`. With default trust_threshold=0.80, `reproducibility_score=0.5` < 0.80 → `trust_breach` fires, producing `block`. The scenario should document this expectation explicitly.

A separate note or scenario variant should document what would happen at `trust_threshold=0.40`: pure `indeterminate_failure` only → `require_review`/`warn`. This surfaces the policy-sensitivity risk before it is introduced.

---

## Low-Priority Items

### FPO-CA-08 — Update `align_replay_budget_state` to set individual objective statuses for `budget_status="invalid"`

| Field | Value |
|---|---|
| ID | FPO-CA-08 |
| Finding | L-01 |
| Severity | Low |
| Status | Open |
| Owner | Codex |
| Blocking | No |
| File | `tests/helpers/replay_result_builder.py` |

**What to add:** In `align_replay_budget_state`, when `budget_status == "invalid"`, additionally set each objective's `status` field to `"invalid"`:

```python
if budget_status == "invalid":
    for obj in (objectives if isinstance(objectives, list) else []):
        if isinstance(obj, dict):
            obj["status"] = "invalid"
    budget["budget_status"] = "invalid"
    budget["highest_severity"] = "invalid"
    budget["triggered_conditions"] = []
    budget["reasons"] = []
```

This removes the fixture state inconsistency (objectives saying "healthy" while budget says "invalid").

---

### FPO-CA-09 — Add chaos scenario: `stability_breach + budget_exhausted → freeze (not block)`

| Field | Value |
|---|---|
| ID | FPO-CA-09 |
| Finding | L-02 |
| Severity | Low |
| Status | Open |
| Owner | Codex |
| Blocking | No |
| File | `tests/fixtures/control_loop_chaos_scenarios.json` |

**What to add:** A scenario with `drift_exceed_threshold_rate` above threshold (triggering `stability_breach`), no `trust_breach`, no `indeterminate_failure`, and `budget_status: "exhausted"`.

Expected: `status: "exhausted"`, `response: "freeze"`, `decision: "deny"`, reasons include `["deny_budget_exhausted", "budget_exhausted", "stability_breach"]`.

This verifies that the `budget_exhausted` path's conditional escalation to `"blocked"/"block"` only fires for trust_breach/indeterminate_failure, not for stability_breach alone.

---

## Deferred / Carry-Forward Items

| ID | Description | Trigger to re-evaluate |
|---|---|---|
| FPO-CA-07 | Indeterminate-only + low trust_threshold scenario | trust_threshold made policy-configurable below 0.5 |
| Prior: deny_indeterminate_failure dead code (2026-03-27-control-loop-trust-boundary-review finding) | Previously identified dead rationale code | Confirm resolution in referenced review |

---

## Summary

| Blocks Merge | FPO-CA-01, FPO-CA-02 |
|---|---|
| Pre-merge recommended | FPO-CA-03, FPO-CA-04 |
| Follow-up | FPO-CA-05, FPO-CA-06, FPO-CA-07, FPO-CA-08, FPO-CA-09 |

**Verdict:** Branch is NOT safe to merge until FPO-CA-01 (description inversion) and FPO-CA-02 (CI gate require_review non-blocking) are resolved. All other items are improvement work for the next iteration.
