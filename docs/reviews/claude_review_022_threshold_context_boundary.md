# Claude Review 022 — Threshold Context Boundary Review

**Review date:** 2026-04-01
**Reviewer:** Claude (reasoning agent)
**Scope:** Surgical post-RED-021 review of the threshold-context boundary between governed runtime decision-making and comparative/analytical policy evaluation.
**Related plan:** `docs/review-actions/PLAN-RED-TEAM-CLOSURE-021-FIX-2026-04-01.md`

---

## Scope Reviewed

Files inspected as primary surface:

| File | Role |
|---|---|
| `spectrum_systems/modules/runtime/evaluation_control.py` | Core threshold resolution, decision mapping, context boundary |
| `spectrum_systems/modules/runtime/policy_backtesting.py` | Comparative caller — policy backtest engine |
| `spectrum_systems/modules/governance/policy_enforcement_integrity.py` | Comparative caller — VAL-10 enforcement integrity matrix |
| `spectrum_systems/modules/governance/end_to_end_failure_simulation.py` | Comparative caller — VAL-08 failure simulation |
| `tests/test_evaluation_control.py` | Boundary tests for threshold context |
| `tests/test_policy_backtesting.py` | Backtesting integration tests |
| `tests/test_policy_backtest_accuracy.py` | VAL-05 accuracy validation |
| `tests/test_policy_enforcement_integrity.py` | VAL-10 integration tests |
| `tests/test_end_to_end_failure_simulation.py` | VAL-08 integration tests |

Out of scope: schema files, orchestration layer, upstream replay engine internals.

---

## What Changed in RED-021

RED-021 added runtime-hardening constraints to `_resolve_governed_thresholds` in `evaluation_control.py` that prevent callers from relaxing `reliability_threshold`, `trust_threshold`, or `drift_threshold` below/above governed defaults. This was correct for the runtime trust spine but broke all comparative/analytical callers (backtesting, enforcement integrity, failure simulation) that intentionally test looser or tighter policy candidates.

The fix introduced:

1. A `ThresholdContext` literal type: `"active_runtime" | "comparative_analysis"`.
2. A `_resolve_threshold_context()` validator that rejects unknown context values.
3. A `_resolve_thresholds()` dispatcher that routes to `_resolve_governed_thresholds` (hardened, with relaxation guards) for runtime and `_resolve_comparative_thresholds` (range-validated only, no relaxation guards) for comparative.
4. A default of `threshold_context="active_runtime"` on `build_evaluation_control_decision`, so any caller that doesn't opt in explicitly gets the hardened path.
5. All comparative callers (`policy_backtesting.py`, `policy_enforcement_integrity.py`, `end_to_end_failure_simulation.py`) were updated to pass `threshold_context="comparative_analysis"` explicitly.

---

## Architectural Judgment

**The seam is sound.** The fix is conceptually correct, minimal, and placed at the right level of abstraction. The default-to-runtime design is the right call. The Literal type plus runtime validation is a reasonable belt-and-suspenders approach.

It is not fragile, but it has two structural gaps that should be closed before more work accumulates on top of it.

---

## Findings

### Strengths

1. **Default is hardened.** `threshold_context` defaults to `"active_runtime"`. Any new caller that forgets to specify context gets the governed path. This is the single most important design decision in the fix and it is correct.

2. **Fail-closed on unknown context.** `_resolve_threshold_context` rejects anything outside the two known values. A typo or accidental string gets an immediate `EvaluationControlError`. Good.

3. **Relaxation guards are runtime-only.** `_resolve_governed_thresholds` prevents weakening below defaults. `_resolve_comparative_thresholds` allows any value in `[0.0, 1.0]`. This is the correct asymmetry.

4. **Single dispatch point.** All threshold resolution flows through `_resolve_thresholds`, which is the only function that inspects `threshold_context`. There is no secondary or shadow dispatch path. Clean.

5. **Callers are explicit.** Every comparative caller passes `threshold_context="comparative_analysis"` at the call site. No implicit inference, no environment variable, no config file. The intent is visible in the code.

6. **Validation is identical for key shape.** Both `_resolve_governed_thresholds` and `_resolve_comparative_thresholds` reject unknown keys and non-numeric values. The only difference is the relaxation guard. This is correct.

### Weaknesses

1. **Output artifact does not carry context provenance.** The `evaluation_control_decision` emitted by `build_evaluation_control_decision` includes a `threshold_snapshot` but does NOT include the `threshold_context` that produced it. A downstream consumer receiving this artifact cannot distinguish a runtime decision from a comparative decision by inspecting the artifact alone. This is a trust-boundary gap: an artifact produced under `comparative_analysis` thresholds looks identical to one produced under `active_runtime` thresholds.

2. **`_resolve_comparative_thresholds` is a near-clone of `_resolve_governed_thresholds`.** The two functions share ~15 lines of identical key-validation and range-checking logic, differing only in the final relaxation guard block. This is tolerable today but will drift if either function is modified independently.

3. **`build_evaluation_control_decision` is a 190-line function** handling four artifact types, budget overrides, signal classification, and schema validation. The threshold context boundary is one parameter on an already-overloaded interface. The function's complexity makes it harder to audit whether the context boundary is respected end-to-end through all branches.

### Hidden Risks

1. **Context laundering via artifact reuse.** If a comparative-context decision artifact is persisted and later consumed by a runtime path that trusts `evaluation_control_decision` artifacts at face value, the comparative thresholds would be treated as runtime thresholds. The artifact itself provides no defense against this because it lacks a `threshold_context` field. **This is the highest-priority gap.**

2. **No structural prevention of `"comparative_analysis"` in runtime callers.** The boundary is enforced by convention (callers pass the right string) not by module topology. Nothing prevents a future runtime module from importing `build_evaluation_control_decision` and passing `threshold_context="comparative_analysis"`. The Literal type helps with static analysis but provides no runtime module-boundary enforcement.

3. **Budget enforcement asymmetry is invisible.** `_enforce_budget_authority` runs for all non-`failure_eval_case` paths regardless of `threshold_context`. This means comparative decisions still get budget enforcement, which is correct for backtesting accuracy, but this invariant is not documented or tested explicitly. If someone removes budget enforcement "for comparative mode" in the future, they would silently weaken backtesting accuracy validation.

---

## Boundary Assessment

### Runtime Path

- Thresholds resolved via `_resolve_governed_thresholds` with relaxation guards: **correct**.
- Default context is `"active_runtime"`: **correct**.
- Unknown context values rejected: **correct**.
- Budget enforcement applied: **correct**.
- Output artifact does not carry context tag: **gap** (see Hidden Risk 1).

### Comparative / Backtesting Path

- All three comparative callers (`policy_backtesting.py:195,200`, `policy_enforcement_integrity.py:288,289,489`, `end_to_end_failure_simulation.py:348`) explicitly pass `threshold_context="comparative_analysis"`: **correct**.
- Thresholds resolved via `_resolve_comparative_thresholds` with range validation only: **correct**.
- Budget enforcement still applied in comparative mode: **correct** (preserves backtesting accuracy).
- No separate entrypoint or wrapper: **acceptable tradeoff** for now. The single-function approach avoids API surface proliferation at the cost of a larger function signature.

### Remaining Ambiguities

1. **Can a comparative decision be promoted to runtime authority?** The current architecture does not answer this question. The artifact schema does not distinguish the two. This ambiguity should be resolved before any pipeline consumes `evaluation_control_decision` artifacts from both paths.

2. **Should comparative decisions carry a different `schema_version`?** Currently both paths emit `schema_version: "1.1.0"`. A version or tag distinction would make the boundary machine-enforceable at the artifact level.

---

## Test Coverage Assessment

**Existing tests that prove the boundary:**

| Test | What it proves |
|---|---|
| `test_active_runtime_rejects_relaxed_thresholds` | Runtime path blocks relaxation below defaults |
| `test_comparative_analysis_allows_relaxed_thresholds` | Comparative path accepts relaxed thresholds |
| `test_threshold_context_is_explicit_and_fail_closed` | Unknown context string rejected |
| `test_malformed_threshold_payload_fails_closed_in_both_contexts` | Bad input rejected in both paths |

**Existing tests that prove comparative callers work:**

- `test_policy_backtesting.py`: 7 tests covering backtest scenarios — all pass through `comparative_analysis` context.
- `test_policy_enforcement_integrity.py`: 7 tests covering VAL-10 matrix — comparative calls in VAL10-C, VAL10-F, VAL10-H.
- `test_end_to_end_failure_simulation.py`: 8 tests covering VAL-08 simulation — comparative call in VAL08-F.

**Missing tests (concrete gaps):**

1. **No test that a comparative-context decision artifact is tagged or distinguishable from a runtime-context decision.** This test cannot be written until the output artifact carries context provenance. This is the test that should drive the schema change in Weakness 1.

2. **No test that `threshold_context="active_runtime"` with tightened thresholds (stricter than defaults) succeeds.** Current tests only verify that relaxation is blocked. Tightening should be allowed and explicitly tested.

3. **No regression guard that a new caller of `build_evaluation_control_decision` without `threshold_context` gets `active_runtime` behavior.** A test should explicitly verify the default parameter value.

4. **No test that budget enforcement is preserved in comparative mode.** The invariant exists in the code but is not tested in isolation.

---

## Recommended Changes

### Must Do Now

**MN-1: Add `threshold_context` to the output artifact.**

Add a `"threshold_context"` field to the `evaluation_control_decision` artifact emitted by `build_evaluation_control_decision`. Value must be `"active_runtime"` or `"comparative_analysis"`, matching the input parameter. Update `evaluation_control_decision.schema.json` to include this field as required. This closes the context-laundering risk (Hidden Risk 1) and makes the boundary machine-enforceable at the artifact level.

**MN-2: Add a regression test for the default `threshold_context` value.**

Write a test that calls `build_evaluation_control_decision(replay)` without any `threshold_context` argument and asserts the resulting decision would reject relaxed thresholds. This guards against accidental default changes.

### Should Do Soon

**SS-1: Extract shared threshold validation into a common helper.**

Factor the key-validation and range-checking logic shared between `_resolve_governed_thresholds` and `_resolve_comparative_thresholds` into a `_validate_threshold_overrides(thresholds)` helper. Keep the relaxation guard in the governed function only. Reduces clone drift risk (Weakness 2).

**SS-2: Add a test that tightened thresholds succeed in runtime context.**

Verify that `threshold_context="active_runtime"` with `reliability_threshold=0.95` (stricter than 0.85 default) produces a valid decision. This proves the runtime path only blocks relaxation, not tightening.

**SS-3: Add a test that budget enforcement fires in comparative context.**

Verify that a comparative-context decision with `budget_status="exhausted"` still produces `deny`. This documents the intentional asymmetry.

### Can Wait

**CW-1: Consider a `ComparativeDecisionBuilder` wrapper.**

If `build_evaluation_control_decision` continues to accumulate parameters, consider extracting a thin `build_comparative_decision(signal_artifact, thresholds)` wrapper that hard-codes `threshold_context="comparative_analysis"` and annotates the output. This would reduce call-site ceremony in comparative callers and make grep-ability easier. Not urgent — the current approach works.

**CW-2: Consider `schema_version` differentiation.**

Emitting `schema_version: "1.1.0-comparative"` or a `"context_tag"` field would allow downstream schema validators to enforce the boundary at the contract level. Only valuable if the artifact pipeline starts mixing runtime and comparative decisions in the same store.

---

## Suggested Follow-On Prompt

```
SCOPE: Surgical schema + code change to close the threshold-context provenance gap identified in Claude Review 022.

TASK:
1. In `contracts/schemas/evaluation_control_decision.schema.json`, add a required field `"threshold_context"` with enum `["active_runtime", "comparative_analysis"]`.
2. In `spectrum_systems/modules/runtime/evaluation_control.py`, in `build_evaluation_control_decision`, add `"threshold_context": threshold_context` to the `decision` dict (around line 537, next to `"threshold_snapshot"`).
3. In `tests/test_evaluation_control.py`, add three tests:
   a. `test_default_threshold_context_is_active_runtime` — call without threshold_context, assert output `threshold_context == "active_runtime"`.
   b. `test_comparative_decision_carries_context_tag` — call with threshold_context="comparative_analysis", assert output `threshold_context == "comparative_analysis"`.
   c. `test_runtime_tightened_thresholds_succeed` — call with threshold_context="active_runtime" and reliability_threshold=0.95, assert valid decision.
4. Run `pytest -q tests/test_evaluation_control.py tests/test_policy_backtesting.py tests/test_policy_backtest_accuracy.py tests/test_policy_enforcement_integrity.py tests/test_end_to_end_failure_simulation.py` and fix any schema-validation failures in existing tests caused by the new required field.

CONSTRAINTS:
- Do not change threshold resolution logic.
- Do not change any function signatures.
- Do not modify any file outside the three listed above plus the schema.
```

---

## Verdict

**ACCEPT WITH HARDENING**

The threshold-context boundary is architecturally sound, correctly placed, and fail-closed by default. The fix addresses the RED-021 root cause without over-engineering. The two must-do items (output artifact provenance and default-value regression guard) should be completed before additional work builds on this seam, as the context-laundering risk is a real trust-boundary gap that becomes harder to fix later.
