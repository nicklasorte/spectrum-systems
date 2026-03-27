# Review Action Tracker

- **Source Review:** `docs/reviews/2026-03-27-control-loop-chaos-eval-gate-review.md`
- **Review ID:** CLR-2026-03-27-001
- **Owner:** Codex (execution agent)
- **Last Updated:** 2026-03-27

---

## Critical Items

| ID | Action Item | Owner | Status | Rationale | Exact Files Touched |
|---|---|---|---|---|---|
| CR-1 | Repair `error_budget_status.objectives.observed_value` consistency in chaos fixture scenarios | Codex | Open | All non-baseline scenarios (`threshold-001`, `threshold-002`, `threshold-003`, `indeterminate-001`) have `observability_metrics.metrics` values that diverge from baseline but leave `error_budget_status.objectives[*].observed_value` frozen at the example baseline. This violates replay artifact internal consistency — the trust boundary. Specifically: each objective's `observed_value`, `consumed_error`, `remaining_error`, `consumption_ratio`, and `status` must reflect the actual patched metric value. `budget_status` and `highest_severity` must also reflect the true state (e.g., `threshold-003` with `drift_exceed_threshold_rate = 0.2001` should have `budget_status = "exhausted"` or `"warning"` and drift objective `status = "warning"` or `"exhausted"`, not `"healthy"`). For `indeterminate-001`: `budget_status` must not be `"healthy"` when `consistency_status = "indeterminate"`. | `tests/fixtures/control_loop_chaos_scenarios.json` |
| CR-2 | Repair `test_precedence_rules_are_explicitly_enforced` to keep error_budget_status in sync with patched metrics | Codex | Open | The parametrize test patches `observability_metrics.metrics` in place but does not update the paired `error_budget_status.objectives[*].observed_value` or `budget_status`. The in-memory fixture becomes internally inconsistent. Must update budget fields when patching metrics. Preferred fix: extend `make_canonical_replay_result` with an optional `budget_patch` parameter that accepts `{"observed_values": {...}, "budget_status": "..."}` and applies those to the budget sub-document; then use this in `test_precedence_rules_are_explicitly_enforced` when building each parametrize case. | `tests/test_control_loop_chaos.py`, `tests/helpers/replay_result_builder.py` |

---

## High-Priority Items

| ID | Action Item | Owner | Status | Rationale | Exact Files Touched |
|---|---|---|---|---|---|
| HI-1 | Correct `invalid-003` fixture description to match actual failure mode | Codex | Open | Scenario `invalid-003` description reads "Invalid enum in system_status is rejected and fails closed." This is wrong. The actual failure is a `trace_refs.trace_id` mismatch: `error_budget_status.trace_refs.trace_id = "mismatch-trace"` does not match `replay_result.trace_id = "33333333-3333-4333-8333-333333333333"`. The runtime raises `REPLAY_INVALID_TRACE_LINKAGE: error_budget_status trace mismatch`. The test passes (expected_reasons = `["control_loop_error"]` is satisfied), but the documented failure mode is wrong. Update `description` to accurately state the trace linkage defect. | `tests/fixtures/control_loop_chaos_scenarios.json` |

---

## Medium-Priority Items

| ID | Action Item | Owner | Status | Rationale | Exact Files Touched |
|---|---|---|---|---|---|
| MI-1 | Investigate and optionally correct `budget_status: "blocked"` → `"invalid"` mapping in `_build_replay_result_from_eval_summary` | Codex | Open | In `run_eval_ci_gate.py:150–153`, `eval_summary.system_status = "blocked"` maps to `error_budget_status.budget_status = "invalid"` because `"blocked"` is not in the allowed set `{"healthy", "warning", "exhausted", "invalid"}`. This causes a status information loss in the constructed replay_result: a governance block looks like an invalid artifact rather than a blocked system. The downstream `evaluation_control.py` handles this gracefully via fallback to `"blocked"` in `map_status_to_response`, so there is no current test failure. However, the mapping is semantically incorrect. If `"blocked"` is a meaningful budget state (distinct from `"invalid"`), the allowed set or the mapping logic should be updated. No test changes are needed unless the schema formally adds `"blocked"` as a valid `budget_status` enum value. Verify against `contracts/schemas/error_budget_status.schema.json`. | `scripts/run_eval_ci_gate.py` |

---

## Low-Priority Items

| ID | Action Item | Owner | Status | Rationale | Exact Files Touched |
|---|---|---|---|---|---|
| LI-1 | Add a note to `make_canonical_replay_result` docstring that callers must keep `error_budget_status` consistent with any `observability_metrics.metrics` overrides | Codex | Open | The builder does not document the invariant that `error_budget_status.objectives[*].observed_value` must match the embedded `observability_metrics.metrics` values. This is what allowed the latent inconsistency in `test_precedence_rules_are_explicitly_enforced` to go undetected. Adding a docstring note reduces the likelihood of the same defect recurring. Does not change runtime behavior. | `tests/helpers/replay_result_builder.py` |

---

## Blocking Items

None. All fixes are additive fixture/test corrections that do not block any other work. The runtime code is correct and must not be modified as part of this action set.

---

## Deferred Items

- **Semantic consistency validation in runtime:** Whether the runtime should eventually enforce that `error_budget_status.objectives[*].observed_value` values are consistent with `observability_metrics.metrics` values is an open design question. This is deferred until a formal contract review determines whether semantic cross-artifact consistency checking belongs at the runtime seam or at the ingestion/production boundary. Do not add this to the runtime without a governed contract decision.

- **Formal schema relationship between budget_status and consistency_status:** Whether `consistency_status = "indeterminate"` should constrain allowable `error_budget_status.budget_status` values is a schema governance question. Deferred to a schema design review.

---

## Do-Not-Change Constraints (for Codex)

These items were reviewed and confirmed correct. Codex must not modify them:

1. `control_loop.py:_validate_normalized_signal` — error message "normalized signal missing required field" is the correct first-gate assertion for malformed replay inputs.
2. `evaluation_control.py` trace linkage checks (lines 133–140) — correctly calibrated.
3. `evaluation_control.py` decision derivation path — computes from raw metrics and `consistency_status`, not from `budget_status` or `objectives.observed_value`.
4. `run_eval_ci_gate.py` exit-code logic — exit 2 for `control_decision_blocked`, exit 1 for threshold-only failures.
5. `control_loop_chaos.py:_evaluate_once` exception catch — fail-closed catch-all is correct.
6. `tests/test_eval_ci_gate.py` assertions — all exit code assertions are correct; no changes needed.
7. `tests/test_control_loop_chaos.py:65–74` (`test_fail_closed_on_malformed_input`) — do not change the expected_signal to a deeper error message.
