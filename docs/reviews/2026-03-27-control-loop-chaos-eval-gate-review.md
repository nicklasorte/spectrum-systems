---
review_id: CLR-2026-03-27-001
review_date: 2026-03-27
repository: nicklasorte/spectrum-systems
reviewer: Claude (Reasoning Agent — Sonnet 4.6)
review_type: targeted_surgical
verdict: CONCERNS
prior_review_refs:
  - docs/reviews/2026-03-22-control-loop-enforcement-review.md
  - docs/2026-03-22-control-loop-enforcement-review.md
inputs_consulted:
  - spectrum_systems/modules/runtime/control_loop.py
  - spectrum_systems/modules/runtime/control_loop_chaos.py
  - spectrum_systems/modules/runtime/evaluation_control.py
  - scripts/run_control_loop_chaos_tests.py
  - scripts/run_eval_ci_gate.py
  - tests/test_control_loop_chaos.py
  - tests/test_eval_ci_gate.py
  - tests/helpers/replay_result_builder.py
  - tests/fixtures/control_loop_chaos_scenarios.json (sampled)
  - contracts/examples/observability_metrics.json
  - contracts/examples/error_budget_status.json
---

# Targeted Review: Control-Loop Chaos / Eval CI Gate Seam

**Date:** 2026-03-27
**Verdict:** CONCERNS
**Reviewer:** Claude (Reasoning Agent — Sonnet 4.6)
**Scope:** Narrow — chaos test fixture consistency, control-loop validation semantics, eval CI gate exit-code contract.

---

## Scope

**In scope:**
- Whether chaos test fixtures maintain internal consistency between `observability_metrics.metrics` and `error_budget_status.objectives.observed_value`
- Whether `control_loop.py` / `evaluation_control.py` runtime validation is correctly calibrated (not over-strict, not under-strict)
- Whether `test_fail_closed_on_malformed_input` assertion targets the correct error message
- Whether eval CI gate exit-code semantics (0/1/2) are correctly implemented and tested

**Out of scope:**
- Full architecture review
- Schema evolution or versioning strategy
- Any system outside the listed primary and secondary files
- Cross-repo enforcement

---

## Summary

- The runtime (`control_loop.py`, `evaluation_control.py`) is **correct**. It fails closed on artifact identity/linkage violations and independently re-derives all threshold decisions from raw metrics. It should not be changed.
- Chaos fixture scenarios and the `test_precedence_rules_are_explicitly_enforced` parametrize test contain a **latent fixture consistency defect**: `observability_metrics.metrics` values are non-default but `error_budget_status.objectives.observed_value` fields remain frozen at canonical-example baseline values. This does not cause current test failures because the runtime does not read `objectives.observed_value` for control decisions, but it violates the replay artifact internal consistency trust boundary.
- The `invalid-003` chaos scenario has a **wrong description** — the fixture fails for a trace linkage reason, not an enum reason.
- `test_fail_closed_on_malformed_input` asserts the correct first-gate error. **Do not change this test.**
- Eval CI gate exit-code semantics are **correctly implemented and tested**.

---

## Findings

### F-1 — LATENT FIXTURE DEFECT: error_budget_status.objectives.observed_value not updated when metrics are patched

**Files:** `tests/fixtures/control_loop_chaos_scenarios.json` (scenarios `threshold-001`, `threshold-002`, `threshold-003`, `indeterminate-001`), `tests/test_control_loop_chaos.py:96–107`

**Description:**

Every non-baseline scenario in the chaos fixture and every case in `test_precedence_rules_are_explicitly_enforced` changes `observability_metrics.metrics` values (e.g., `replay_success_rate`, `drift_exceed_threshold_rate`) but leaves `error_budget_status.objectives[*].observed_value` frozen at the canonical example baseline:
- `observed_value: 1.0` for `replay_success_rate`
- `observed_value: 0.0` for `drift_exceed_threshold_rate`

**Concrete examples:**

| Scenario | metrics.replay_success_rate | metrics.drift_exceed_threshold_rate | objectives.observed_value (success) | objectives.observed_value (drift) | budget_status |
|---|---|---|---|---|---|
| `threshold-001` | 0.85 | 0.20 | **1.0** ← stale | **0.0** ← stale | healthy |
| `threshold-002` | 0.8499 | 0.02 | **1.0** ← stale | **0.0** ← stale | healthy |
| `threshold-003` | 0.95 | 0.2001 | **1.0** ← stale | **0.0** ← stale | **healthy** ← wrong: should reflect drift breach |
| `indeterminate-001` | 1.0 | 0.0 | 1.0 | 0.0 | **healthy** ← wrong: should reflect indeterminate status |

In `test_precedence_rules_are_explicitly_enforced` (line 101–102), the test only does:
```python
replay["observability_metrics"]["metrics"].update(replay_patch["observability_metrics"]["metrics"])
```
It does not update `error_budget_status.objectives[*].observed_value` or `error_budget_status.budget_status`.

**Why it does not currently cause failures:**

`evaluation_control.py::_to_eval_summary_from_replay_result` computes the three control inputs exclusively from:
1. `observability_metrics.metrics.replay_success_rate` → `pass_rate`
2. `observability_metrics.metrics.drift_exceed_threshold_rate` → `drift_rate`
3. `replay_result.consistency_status` → `reproducibility_score` (via hard-coded mapping: match=1.0, mismatch=0.0, indeterminate=0.5)

`error_budget_status.budget_status` feeds only `eval_summary["system_status"]` which is NOT subsequently read by `build_evaluation_control_decision` for threshold comparisons. `objectives[*].observed_value` is not read at all for decision computation.

**Why it is still a defect:**

The replay artifact is a trust boundary. The contract requires that `error_budget_status` accurately reflects the observability metrics it is linked to. A `budget_status: "healthy"` alongside a drift rate of `0.2001` (above the drift threshold, triggering `stability_breach → freeze`) is an internally inconsistent artifact. If a future validator adds semantic consistency checks (or if a downstream consumer reads `budget_status` directly), these tests will produce wrong results silently.

For `indeterminate-001`: `consistency_status = "indeterminate"` but `budget_status = "healthy"` and `objectives` show fully healthy values. The artifact says the system is healthy while simultaneously recording an indeterminate replay consistency outcome. This is a contract violation at the fixture level.

**Classification:** Test fixture defect. Runtime is correct. Tests need updating, not the runtime.

---

### F-2 — FIXTURE DOCUMENTATION DEFECT: invalid-003 description claims wrong failure mode

**File:** `tests/fixtures/control_loop_chaos_scenarios.json` (scenario `invalid-003`)

**Description:**

The `description` field reads:
> "Invalid enum in system_status is rejected and fails closed."

This is incorrect. There is no invalid enum in `system_status` in this artifact. `budget_status = "healthy"` is valid. The actual failure mode is a `trace_refs.trace_id` mismatch:
- `replay_result.trace_id = "33333333-3333-4333-8333-333333333333"`
- `error_budget_status.trace_refs.trace_id = "mismatch-trace"` ← does not match

`evaluation_control.py:135` detects this and raises:
```
REPLAY_INVALID_TRACE_LINKAGE: error_budget_status trace mismatch
```

The scenario correctly produces `"control_loop_error"` as the actual reason (matching `expected_reasons`), so the test passes. But the stated failure mode in the description is wrong, making this scenario misleading as documentation.

**Classification:** Fixture documentation defect. Test passes for the wrong stated reason.

---

### F-3 — CONFIRMED CORRECT: runtime validation correctly fails closed on identity/linkage, not on semantic consistency

**Files:** `spectrum_systems/modules/runtime/evaluation_control.py:130–140`, `spectrum_systems/modules/runtime/control_loop.py:62–87`

**Analysis:**

The runtime enforces two cross-artifact checks:
1. **Trace linkage** (line 133, 135): `observability_metrics.trace_refs.trace_id` and `error_budget_status.trace_refs.trace_id` must both match `replay_result.trace_id`
2. **Artifact lineage** (line 137): `error_budget_status.observability_metrics_id` must equal `observability_metrics.artifact_id`

These checks correctly enforce that the artifact triple (`replay_result`, `observability_metrics`, `error_budget_status`) belongs to the same run and that the budget was computed from the referenced observability artifact.

The runtime does **not** enforce semantic consistency between `observability_metrics.metrics` values and `error_budget_status.objectives.observed_value` — and this is appropriate. The runtime is not in a position to re-derive whether the budget system produced the correct `observed_value` entries. It trusts that the artifact was correctly produced by the budget system; it only verifies identity binding.

**Verdict:** The runtime is correct to fail closed on identity/linkage mismatches. It is NOT over-strict. The current validation boundary is appropriate. Do not loosen it, and do not extend it to recheck semantic consistency.

---

### F-4 — CONFIRMED CORRECT: test_fail_closed_on_malformed_input asserts the right first-gate error

**File:** `tests/test_control_loop_chaos.py:65–74`

**Analysis:**

The test case:
```python
({"artifact_type": "replay_result", "replay_id": "x"}, "normalized signal missing required field"),
```

Trace through `run_control_loop` for this input:
1. `_normalize_signal` succeeds — produces `signal` with `source_artifact_id = "x"`, `trace_id = ""`, `run_id = ""`
2. `_validate_normalized_signal` — `signal["trace_id"] = ""` → fails: `"normalized signal missing required field: trace_id"`

This is the correct first gate for this input. The error is raised before `_validate_trace_context_binding` or `_evaluate_signal`. The test assertion matches the current first-gate error message.

**This test should not be changed.** If the artifact is enriched with `trace_id` and `replay_run_id` but remains otherwise malformed, the error will shift to a deeper message from `evaluation_control.py`. That would be a new test case, not a modification to this one.

**Verdict:** Test assertion is correct for the current input. Asserting the legacy generic error message is correct here because `_validate_normalized_signal` fires before the deeper validation.

---

### F-5 — CONFIRMED CORRECT: eval CI gate exit-code semantics and test assertions match

**File:** `scripts/run_eval_ci_gate.py:393–414`, `tests/test_eval_ci_gate.py`

**Intended semantics (confirmed from implementation):**

| Exit code | Status label | Condition |
|---|---|---|
| 0 | `pass` | No blocking reasons |
| 1 | `fail` | Blocking reasons exist AND all of them are `threshold_failed:*` |
| 2 | `blocked` | Any blocking reason that is NOT `threshold_failed:*`, or mixed threshold + non-threshold |

The logic in `run_eval_ci_gate.py:396–405`:
```python
only_threshold_failures = threshold_failed and all(
    reason.startswith("threshold_failed:") for reason in blocking_reasons
)
if only_threshold_failures:
    status = "fail"; exit_code = 1
else:
    status = "blocked"; exit_code = 2
```

This is semantically clean and correct. `control_decision_blocked:*` reasons always produce exit 2 (they are not threshold failures). `threshold_failed:*` reasons alone produce exit 1.

**Test assertions are all correct:**
- `test_threshold_failure_fails_closed` → exit 1 ✓ (only threshold failures)
- `test_blocking_control_decision_fails_closed` → exit 2 ✓ (`control_decision_blocked:` reason, no threshold failures)
- `test_indeterminate_eval_outcome_fails_closed` → exit 2 ✓ (`indeterminate_eval_outcome_detected`)
- `test_missing_required_artifact_fails_closed` → exit 2 ✓ (`missing_required_artifact:`)
- `test_invalid_schema_artifact_fails_closed` → exit 2 ✓ (`invalid_schema:`)
- `test_indeterminate_can_be_explicitly_overridden_by_policy` → exit 1 ✓ (indeterminate suppressed, residual threshold failures only)

**Verdict:** Implementation and tests are aligned. No changes required.

---

### F-6 — SECONDARY LATENT: budget_status "blocked" → "invalid" round-trip in run_eval_ci_gate.py

**File:** `scripts/run_eval_ci_gate.py:150–153`

**Description:**

`_build_replay_result_from_eval_summary` maps `eval_summary.system_status` → `error_budget_status.budget_status`:
```python
summary_status = str(eval_summary.get("system_status") or "blocked")
replay_result["error_budget_status"]["budget_status"] = (
    summary_status if summary_status in {"healthy", "warning", "exhausted", "invalid"} else "invalid"
)
```

`"blocked"` is not in the allowed set `{"healthy", "warning", "exhausted", "invalid"}`, so it maps to `"invalid"`. But `"blocked"` is the correct system status when the eval_summary reflects a governance block. This creates an information loss: a blocked system outcome becomes `budget_status = "invalid"` in the constructed replay_result.

`evaluation_control.py` then reads `error_budget.get("budget_status")` back as `"invalid"` → which maps to `system_status = "invalid"` in the eval_summary → which hits the fallback in `map_status_to_response` (`"blocked"`) → which is fine for the control decision.

This is not currently causing test failures because the control decision is still derived from triggered_signals. But the semantic representation of `budget_status = "invalid"` for a `"blocked"` governance condition is misleading. This is a lower-priority issue but represents an incomplete status mapping contract.

**Classification:** Secondary latent defect. Low priority. Does not affect test correctness.

---

## Root Cause Classification

| ID | Root Cause Category | Finding(s) | Active Failure? |
|---|---|---|---|
| RC-1 | Test fixture internal consistency defect | F-1 (latent metric/budget mismatch) | No — latent |
| RC-2 | Fixture documentation defect | F-2 (invalid-003 wrong description) | No — passes for wrong reason |
| RC-3 | Runtime validation is correct | F-3 | N/A — no defect |
| RC-4 | Test assertion is correct | F-4 | N/A — no defect |
| RC-5 | Gate semantics correct and tests aligned | F-5 | N/A — no defect |
| RC-6 | Secondary status mapping gap | F-6 | No — latent |

**Direct answer to the four scoped questions:**

1. **Stale or invalid chaos/gate tests?** Partially yes — `invalid-003` has a stale/wrong description, and all non-baseline chaos scenarios and the parametrize test have stale `error_budget_status.objectives.observed_value` fields. These do not cause current failures but are trust-boundary violations.

2. **Over-strict runtime validation?** No. The control loop fails closed on identity/linkage mismatches; this is correct and should not change.

3. **Real contract mismatch between replay_result, observability_metrics, and error_budget_status?** Yes, but only at the fixture level, not in the runtime contract. The fixtures violate internal consistency of the replay artifact contract. The runtime contract itself is correctly implemented.

4. **Incorrect eval CI gate exit-code semantics?** No. Exit 2 for `control_decision_blocked`, exit 1 for threshold failures only. Both implementation and tests are correct.

---

## Minimum Safe Fix Set

The following changes are necessary and sufficient to restore semantic alignment without weakening fail-closed behavior.

### Fix 1 (Required): Update chaos fixture scenarios to keep error_budget_status consistent with observability_metrics.metrics

**Target:** `tests/fixtures/control_loop_chaos_scenarios.json`

For each scenario where `observability_metrics.metrics` contains non-baseline values, update the paired `error_budget_status` to reflect the actual metrics:
- Set `objectives[*].observed_value` to match the corresponding `metrics` value
- Update `objectives[*].consumed_error`, `objectives[*].remaining_error`, `objectives[*].consumption_ratio`, and `objectives[*].status` to reflect the actual deviation from target
- Update `budget_status` and `highest_severity` to reflect the true budget state given the patched metrics

Affected scenarios: `threshold-001`, `threshold-002`, `threshold-003`, `indeterminate-001`.

For `indeterminate-001` specifically: `budget_status` should be `"exhausted"` or `"invalid"` (not `"healthy"`) because `consistency_status = "indeterminate"` represents a failed replay. The `objectives.status` for `replay_success_rate` should also not be `"healthy"` given an indeterminate outcome.

**Important:** These fixture changes do NOT affect control decision outputs because the runtime does not read `objectives.observed_value`. They restore internal consistency of the replay artifact to respect the trust boundary.

### Fix 2 (Required): Update test_precedence_rules_are_explicitly_enforced to keep error_budget_status consistent

**Target:** `tests/test_control_loop_chaos.py:96–107`

When patching `observability_metrics.metrics`, also update the paired `error_budget_status` fields in the in-memory fixture:
- `error_budget_status.objectives[*].observed_value`
- `error_budget_status.budget_status`

The `_base_replay_result()` builder provides a dict; the test should update budget fields alongside metric fields when constructing the patched artifact. Consider extending `make_canonical_replay_result` or adding a helper to keep both sides in sync.

### Fix 3 (Required): Correct invalid-003 fixture description

**Target:** `tests/fixtures/control_loop_chaos_scenarios.json`, scenario `invalid-003`

Update `description` from:
> "Invalid enum in system_status is rejected and fails closed."

To something accurate, e.g.:
> "error_budget_status trace_refs.trace_id mismatch triggers REPLAY_INVALID_TRACE_LINKAGE and fails closed."

---

## What Should Not Be Changed

1. **`control_loop.py:_validate_normalized_signal`** — The "normalized signal missing required field" error is the correct first gate. `test_fail_closed_on_malformed_input` should not be modified to expect a deeper error message.

2. **`evaluation_control.py` trace/lineage checks** — The cross-artifact identity validation is correct and appropriately calibrated. Do not loosen the trace_id binding check or the `observability_metrics_id` lineage check.

3. **`evaluation_control.py` decision derivation path** — Deriving `pass_rate`, `drift_rate`, and `reproducibility_score` from raw metrics and `consistency_status` (not from `error_budget_status.budget_status` or `objectives.observed_value`) is correct behavior and should not change.

4. **`run_eval_ci_gate.py` exit-code logic** — Exit 2 for `control_decision_blocked` and exit 1 for threshold-only failures is the correct and tested semantics. Neither the implementation nor the test assertions should change.

5. **`control_loop_chaos.py:_evaluate_once` error catch** — Catching all `ControlLoopError` / `EvaluationControlError` / `ValueError` / `TypeError` / `KeyError` and mapping to `"control_loop_error"` is correct fail-closed behavior for the chaos runner. No change required.

---

## Recommended Next Step

Hand the three fixes directly to Codex for repair in this order:
1. Fix 3 (trivial documentation fix, zero risk)
2. Fix 1 (fixture data repair — follow the budget computation logic in `error_budget_status.json` example as a template for each patched metric)
3. Fix 2 (test helper extension — consider extending `make_canonical_replay_result` with a `budget_patch` parameter that accepts a dict of metric overrides and recomputes the budget fields accordingly)

After repair, run `pytest tests/test_control_loop_chaos.py tests/test_eval_ci_gate.py` to confirm all tests still pass. The fixes should not change any test outcomes — they restore fixture correctness without changing what the runtime tests.
