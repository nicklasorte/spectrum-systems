# BAF Enforcement Wiring — Trust-Boundary Audit
**Date:** 2026-03-22
**Reviewer:** Claude (Reasoning Agent — Sonnet 4.6)
**Scope:** BAF Enforcement Wiring layer — decision-to-action conversion, enforcement guarantee, state machine integrity, and fail-closed behavior

**Modules reviewed:**
- `spectrum_systems/modules/runtime/enforcement_engine.py`
- `spectrum_systems/modules/runtime/control_integration.py`
- `spectrum_systems/modules/runtime/control_loop.py`
- `spectrum_systems/modules/runtime/evaluation_control.py`
- `spectrum_systems/modules/runtime/replay_engine.py`
- `contracts/schemas/enforcement_result.schema.json`
- `contracts/schemas/evaluation_control_decision.schema.json`

---

## Decision

**FAIL**

The canonical BAF path (`enforce_control_decision`) is structurally sound and schema-governed for `eval_summary` and `failure_eval_case` artifacts. However, two critical defects break the universal fail-closed guarantee: `replay_run` silently absorbs all enforcement failures and returns a soft `indeterminate` value rather than raising, and `enforce_control_before_execution` contains an `else` branch that bypasses BAF entirely for any non-governed artifact type. A third latent fail-open exists in `_execution_result_from_enforcement_result` — its implicit `else "success"` path is currently guarded only by upstream schema validation. Additional findings break traceability and determinism guarantees. None of the three defects are hypothetical; all are reachable under realistic conditions.

---

## Critical Findings

**CF-1 — `replay_run` swallows all enforcement failures and returns soft `indeterminate` (`replay_engine.py:693–694`)**

A bare `except Exception` block wraps the entire control-loop and enforcement execution sequence in `replay_run`, including the calls to `run_control_loop` and `enforce_control_decision`. Any failure in those functions — `EnforcementError`, `ControlLoopError`, schema load failure, or a bad `evaluation_control_decision` — is caught and converted into `_indeterminate(...)`. The return dict has `replay_status="indeterminate"` and `consistency_check_passed=False`. This is not a hard block. It is a return value. The exception is not re-raised and not logged as an error. Callers that treat `indeterminate` as a non-conclusive, non-blocking outcome have a literal fail-open path through a silent enforcement error. The enforcement layer's failure is invisible at the call site.

**CF-2 — Non-governed `else` branch bypasses BAF entirely (`control_integration.py:217–248`)**

`enforce_control_before_execution` gates on `artifact.get("artifact_type") in {"eval_summary", "failure_eval_case"}`. Any artifact that does not match — including all dicts with other `artifact_type` values and all non-dict inputs — routes through `run_control_chain` in the `else` branch. That path does not call `enforce_control_decision`, produces no `enforcement_result` artifact, has no schema-validated enforcement contract, and leaves `enforcement_result` absent from `integration_result`. `continuation_allowed` still defaults to `False` when `execution_status` is missing, so the gate is fail-closed on absence, but the enforcement decision is not governed, not auditable, and not traceable. The BAF trust boundary is conditional on artifact type and is not universal.

**CF-3 — `_execution_result_from_enforcement_result` has no `else` guard for unknown `final_status` (`control_integration.py:104–107`)**

```python
blocked = final_status == "deny"
review_required = final_status == "require_review"
execution_status = "blocked" if (blocked or review_required) else "success"
```

The implicit `else` evaluates to `"success"`, which sets `continuation_allowed=True`. This is currently prevented by `enforce_control_decision` validating its output against the schema, which constrains `final_status` to three values. However, no guard exists in this function itself. If the schema or validator is bypassed, weakened, or misconfigured, any unrecognized `final_status` silently produces `continuation_allowed=True`. This is a latent fail-open with no defense-in-depth at the most critical translation point in the enforcement chain.

**CF-4 — `decision_id` collision for all malformed inputs without `eval_run_id` (`evaluation_control.py:134–143`)**

When `build_evaluation_control_decision` receives an input that fails schema validation and has no `eval_run_id`, the fail-closed decision seeds `_deterministic_decision_id` with `eval_run_id="unknown-eval-run"`. All such inputs produce the identical `decision_id` (`ECD-{sha256("unknown-eval-run|malformed_eval_summary|1.1.0")[:12]}`). The `enforce_control_decision` output uses this as `input_decision_reference`. Multiple distinct enforcement events share the same provenance reference, breaking one-to-one traceability. Under audit or incident reconstruction, multiple blocked enforcement actions for different malformed inputs are indistinguishable by their provenance chain.

**CF-5 — Legacy `enforce_budget_decision` is an active callable with different semantics and no schema alignment (`enforcement_engine.py:142–174`)**

`enforce_budget_decision` produces a result dict with `execution_permitted=True` for both `allow` and `warn` system responses. Its output is not validated against `enforcement_result.schema.json` and is structurally incompatible with the canonical contract — it uses different field names (`enforcement_id`, `enforcement_status`, `execution_permitted`) and carries no `fail_closed` flag. It remains callable without any deprecation guard. Any caller that accidentally or intentionally routes through it receives an enforcement artifact under materially weaker semantics: `warn` permits execution rather than requiring review.

---

## Required Fixes

**CF-1:** Replace the bare `except Exception` in `replay_run` with explicit, typed re-raises. Enforcement and control-loop failures must propagate as hard errors:

```python
except (EnforcementError, ControlLoopError, EvaluationControlError) as exc:
    raise ReplayEngineError(f"enforcement pipeline failed: {exc}") from exc
```

`_indeterminate` must be reserved strictly for structurally invalid input artifacts — never for enforcement execution failures.

**CF-2:** Either (a) reject all non-governed artifact types at the gate with an explicit `raise ContractRuntimeError("unsupported artifact_type: ...")` before any control chain is invoked, or (b) require that `run_control_chain` produce a schema-validated `enforcement_result` as a precondition before its `execution_result` is consumed. The `else` branch must not exist as a silent alternative with unverified enforcement guarantees.

**CF-3:** Add an explicit guard in `_execution_result_from_enforcement_result` that raises rather than defaulting to `"success"`:

```python
if final_status == "allow":
    execution_status = "success"
elif final_status in ("deny", "require_review"):
    execution_status = "blocked"
else:
    raise ContractRuntimeError(f"unrecognized final_status: {final_status!r}")
```

**CF-4:** When `eval_run_id` is absent or empty in a malformed input, generate a unique fallback using a UUID or monotonic token before seeding `_deterministic_decision_id`. The `decision_id` must be unique per enforcement event regardless of whether the input was well-formed.

**CF-5:** Add a `warnings.warn(..., DeprecationWarning)` call at the top of `enforce_budget_decision`. Add a CI assertion or grep gate confirming zero non-test callers. The single active enforcement path must be `enforce_control_decision`.

---

## Optional Improvements

- Add a startup or import-time assertion that `set(_ACTION_MAP.keys()) == set(schema["properties"]["decision"]["enum"])` to prevent silent divergence between the schema's decision enum and the action map as the schema evolves.
- Change `enforce_control_before_execution` to raise `ContractRuntimeError` on invalid context rather than returning a blocked dict. Returning a dict transfers the fail-closed obligation to every caller; raising is a harder and more enforceable guarantee.
- Add a `control_trace` entry to the `else`-branch result so that non-governed executions are at minimum observable in the audit trail.
- Document explicitly in the module docstring which artifact types are governed by BAF and which are not, so the boundary is visible to future callers.

---

## Trust Assessment

**NO.**

The layer cannot be trusted to never allow an invalid or ambiguous decision through. CF-1 is a realistic path where enforcement pipeline failures are silently returned as `indeterminate`, with no exception raised and no hard stop — callers bear the obligation to treat `indeterminate` as a block, which is not enforced by the interface. CF-2 confirms the enforcement guarantee is conditional on artifact type. CF-3 is a latent fail-open dependent entirely on upstream schema validation remaining intact with no redundancy at the translation point. Any of the three is sufficient to fail this audit. All three are present simultaneously.

---

## Failure Mode Summary

**Worst realistic failure today:**

A governed `eval_summary` artifact is submitted to `replay_run` for consistency verification. The `validate_and_emit_decision` step fails due to a corrupt bundle path or a transient schema loading error. The `except Exception` block at `replay_engine.py:693` catches the error and returns `_indeterminate(...)` with `replay_status="indeterminate"`. A caller that checks `record["replay_status"] == "success"` and treats any other outcome as "inconclusive — queue for manual review" continues execution. The enforcement decision that should have blocked this run was never produced. No exception was raised, no error was logged, no hard block was applied. The artifact advances through the pipeline with a deferred review obligation rather than an immediate stop, and the audit trail contains no enforcement result artifact — only an indeterminate replay record.
