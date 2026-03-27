# Control Loop Trust Boundary Review — Action Tracker

- **Source Review:** `docs/reviews/2026-03-27-control-loop-trust-boundary-review.md`
- **Owner:** unassigned
- **Last Updated:** 2026-03-27

---

## Critical Items

| ID | Action Item | Affected Files | Recommended Fix | Owner | Status | Blocking Dependencies | Notes |
|---|---|---|---|---|---|---|---|
| CR-1 | Remove or realign `deny_indeterminate_failure` rationale code — it is unreachable because `consistency_status = "indeterminate"` always produces `reproducibility_score = 0.5` which is below the `trust_threshold = 0.80`, triggering `trust_breach` first in the elif chain | `evaluation_control.py`, `contracts/schemas/evaluation_control_decision.schema.json` | Option A: Remove `deny_indeterminate_failure` from the schema enum and the elif chain in `build_evaluation_control_decision`, and document that indeterminate consistency routes through `deny_trust_breach`. Option B: Modify the `reproducibility_score` mapping for `"indeterminate"` to ≥ 0.80 so `trust_breach` is not co-triggered. Option A is lower-risk. | Codex | closed | None | Closed 2026-03-27: removed dead rationale enum/branch; tests assert indeterminate routes to `deny_trust_breach`. |

---

## High-Priority Items

| ID | Action Item | Affected Files | Recommended Fix | Owner | Status | Blocking Dependencies | Notes |
|---|---|---|---|---|---|---|---|
| HI-1 | `enforce_control_before_execution` raises `ContractRuntimeError` instead of returning a blocked integration_result when `EvalCaseGenerationError` occurs during blocked-path eval case generation (lines 325–345) — breaks the "always return dict" contract, skips observability log, and callers cannot inspect the partial result | `spectrum_systems/modules/runtime/control_integration.py` | Catch `EvalCaseGenerationError`, attach error detail to `integration_result["generated_failure_eval_case_error"]`, and fall through to `_log_integration_outcome` and return. Never re-raise from this path. | Codex | closed | None | Closed 2026-03-27: blocked path now returns deterministic integration_result with structured `generated_failure_eval_case_error` and logs secondary failure. |
| HI-2 | `_normalize_signal` builds `decision_inputs = {consistency_status, has_observability_metrics, has_error_budget_status}` which is never consumed — `_evaluate_signal` ignores the normalized signal and passes raw artifact directly to `build_evaluation_control_decision`, making `decision_inputs` dead logic | `spectrum_systems/modules/runtime/control_loop.py` | Either (a) remove `decision_inputs` from the normalized signal return value entirely, or (b) promote `has_observability_metrics` and `has_error_budget_status` into explicit pre-evaluation gates that raise `ControlLoopError` before `_evaluate_signal` is called | unassigned | open | None | Creates false pre-validation confidence; actual presence checks happen downstream inside `build_evaluation_control_decision` |
| HI-3 | `require_review` enforcement maps to `publication_blocked = False` and `decision_blocked = False` while `continuation_allowed = False` and `execution_status = "blocked"` — callers reading only `publication_blocked` could incorrectly treat a pending-review artifact as safe to publish | `spectrum_systems/modules/runtime/control_integration.py` | Set `publication_blocked = True` and `decision_blocked = True` for `require_review` in `_execution_result_from_enforcement_result`, keeping `human_review_required = True` and `escalation_triggered = False` to preserve semantic distinction from `deny`. Alternatively, add explicit caller assertions in the adapters. | Codex | closed | None | Closed 2026-03-27: `require_review` now blocks publication/decision while preserving `human_review_required=True` and `escalation_triggered=False`. |

---

## Medium-Priority Items

| ID | Action Item | Affected Files | Recommended Fix | Owner | Status | Blocking Dependencies | Notes |
|---|---|---|---|---|---|---|---|
| MI-1 | Chaos test `_build_expectation` silently defaults `expected_decision` to `"deny"` if the field is omitted from a scenario — scenarios testing `require_review` behavior that omit this field will silently produce incorrect expectations | `spectrum_systems/modules/runtime/control_loop_chaos.py` | Add `expected_decision` to the required fields list in `_validate_scenario_shape`. Remove the `"deny"` default from `_build_expectation`. Scenarios without `expected_decision` must raise `ControlLoopChaosError` at load time. | Codex | closed | None | Closed 2026-03-27: scenario validation now requires valid `expected_decision`; omission fails fast with `ControlLoopChaosError`. |
| MI-2 | `agent_golden_path._build_replay_result_for_control` only constructs `consistency_status = "match"` or `"mismatch"` — `"indeterminate"` is never generated, leaving the indeterminate → trust_breach → deny path without golden path regression coverage | `spectrum_systems/modules/runtime/agent_golden_path.py`, chaos scenario corpus | Create at least one chaos scenario fixture with a raw `replay_result` artifact where `consistency_status = "indeterminate"`, `failure_reason` is a non-null string, and `drift_detected = false` (per schema allOf constraints). Confirm the path routes through `deny_trust_breach`. | unassigned | open | CR-1 (confirms which rationale code applies) | Untestable code path; no regression coverage via golden path |
| MI-3 | Chaos `_is_match` reason check is subset-only: `missing_reasons = [item for item in expectation.expected_reasons if item not in actual_reasons]` — actual reasons may include unexpected signal codes without triggering a mismatch | `spectrum_systems/modules/runtime/control_loop_chaos.py` | Replace subset check with exact-set equality: `set(actual.get("reasons") or []) == set(expectation.expected_reasons)`. Add an optional `allow_extra_reasons: true` per-scenario flag for cases where supersets are intentionally acceptable. | Codex | closed | MI-1 | Closed 2026-03-27: default reason matching is exact-set; optional `allow_extra_reasons: true` enables subset matching when explicitly requested. |

---

## Low-Priority Items

| ID | Action Item | Affected Files | Recommended Fix | Owner | Status | Blocking Dependencies | Notes |
|---|---|---|---|---|---|---|---|
| LI-1 | Chaos `_evaluate_once` exception handler covers `(ControlLoopError, EvaluationControlError, ValueError, TypeError, KeyError)` but excludes `AttributeError` and other unexpected exception types — malformed scenario artifacts that trigger these will propagate as unhandled exceptions and abort the chaos runner | `spectrum_systems/modules/runtime/control_loop_chaos.py` | Add `AttributeError` to the caught exception tuple, or use a final `except Exception as exc` fallback that logs the unexpected exception type and returns the standard blocked/deny result with `error = str(exc)` | unassigned | open | None | Chaos runner stability issue; does not affect production paths |

---

## Blocking Items

- **CR-1** must be resolved before any downstream system is built or extended that routes on `rationale_code`. The `deny_indeterminate_failure` code is published in the schema enum and consumers cannot determine its reachability from the schema alone.
- **HI-1** should be resolved before chaos runs or integration test results are used as observability evidence for blocked execution paths. Blocked paths that secondary-fail are currently unlogged.

---

## Deferred Items

- **Custom thresholds injection surface** (`build_evaluation_control_decision` accepts arbitrary `thresholds` dict without pre-validation; out-of-range values are only caught post-construction by schema validation). Acceptable given schema enforcement at artifact boundary, but requires a dedicated review if threshold injection becomes runtime-configurable.
- **`enforce_budget_decision` legacy caller allowlist** (uses Python stack-frame inspection which is fragile under refactoring). Deferred to a legacy-surface review.
