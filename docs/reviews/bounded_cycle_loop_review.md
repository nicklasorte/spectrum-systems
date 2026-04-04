# Bounded Cycle Loop Review

- **Review ID**: BCLR-2026-04-04-001
- **Date**: 2026-04-04
- **Scope**: `next_cycle_decision`, `next_cycle_input_bundle`, `cycle_runner_result`, `run_next_governed_cycle`, continuation + program enforcement interaction
- **Reviewer**: Claude (architecture audit agent)

## Summary Judgment

**READY WITH HARDENING**

The bounded cycle loop is structurally sound. The `run_next_governed_cycle` function enforces single-step execution, schema-validates all inputs and outputs, and refuses execution on any precondition failure. The continuation chain (`next_cycle_decision` -> `next_cycle_input_bundle` -> `cycle_runner_result`) is deterministic and traceable. However, five integrity risks require hardening before the loop can be considered production-grade.

---

## Top Risks (Ranked)

### Risk 1

- **Title**: No explicit max-chain-depth bound on multi-invocation continuation
- **Location**: `spectrum_systems/modules/runtime/next_governed_cycle_runner.py:93-261` and `scripts/run_next_governed_cycle.py`
- **Description**: `run_next_governed_cycle` executes exactly one cycle and emits `next_cycle_decision_ref` and `next_cycle_input_bundle_ref` in its result. Nothing in the contract or code prevents an external orchestrator from feeding those refs back into another call to `run_next_governed_cycle` in an unbounded loop. The function itself is single-step, but the system-level chain has no depth counter, TTL, or max-continuation-count.
- **Why it matters**: A misconfigured or adversarial caller can chain governed cycles indefinitely, consuming resources and potentially exhausting roadmap batches without human checkpoint. The boundedness guarantee is local (per-call) but not global (across the chain).
- **Minimal fix**: Add a `cycle_depth` or `continuation_count` field to `next_cycle_input_bundle` (increment on each cycle). Add a `max_continuation_depth` field to the execution policy. `run_next_governed_cycle` refuses if depth exceeds max.

### Risk 2

- **Title**: Timestamp-sourced nondeterminism when `created_at` is omitted
- **Location**: `spectrum_systems/modules/runtime/next_governed_cycle_runner.py:109` (`_utc_now()` fallback)
- **Description**: When `created_at` is not supplied, the runner calls `_utc_now()`. Since `created_at` flows into `_canonical_hash` via the result builder, the `cycle_runner_result_id` becomes nondeterministic. The same logical operation run twice at different wall-clock times produces different artifact IDs.
- **Why it matters**: Replay and determinism verification depend on stable artifact IDs. Nondeterministic IDs break replay chain consistency checks and make audit log correlation fragile.
- **Minimal fix**: Require `created_at` as a mandatory parameter (remove the `None` default) or emit a determinism warning in the result when the fallback is used. Alternatively, exclude `created_at` from the ID hash seed.

### Risk 3

- **Title**: `unresolved_blockers` conflation with `required_reviews` in bundle generation
- **Location**: `spectrum_systems/modules/runtime/system_cycle_operator.py:539`
- **Description**: `_build_next_cycle_input_bundle` populates `unresolved_blockers` as `sorted(set(blocking_conditions + required_reviews))`. This means any required review (even a non-blocking advisory review) is treated as an unresolved blocker. In `run_next_governed_cycle` (line 157), any non-empty `unresolved_blockers` list triggers `execution_precondition_missing`, which refuses execution.
- **Why it matters**: A cycle that has blocking conditions resolved but still carries advisory required reviews will be refused. This is overly conservative and can stall the loop even when the cycle is genuinely ready to proceed.
- **Minimal fix**: Separate `required_reviews` from `unresolved_blockers` in the bundle. Only blocking reviews should be included in `unresolved_blockers`. The schema already has both `active_risks` and `unresolved_blockers` fields; use them distinctly.

### Risk 4

- **Title**: Broad exception swallowing masks root cause on execution failure
- **Location**: `spectrum_systems/modules/runtime/next_governed_cycle_runner.py:201`
- **Description**: The `except (SystemCycleOperatorError, ValueError, TypeError)` block catches three exception types and emits a generic `execution_error` refusal code. The error message is embedded in `emitted_artifact_refs` as `error:{exc}`, which is a string representation that may contain internal state details and is not schema-constrained.
- **Why it matters**: (1) `ValueError` and `TypeError` are extremely broad; they can mask unrelated bugs (e.g., a typo causing a TypeError in candidate scoring). (2) Embedding `error:{exc}` in `emitted_artifact_refs` pollutes the artifact ref namespace with unstructured error strings that may fail downstream schema validation of ref patterns.
- **Minimal fix**: Narrow the except clause to `SystemCycleOperatorError` only. Add a separate `error_detail` field to the result schema. Log `ValueError`/`TypeError` as unexpected failures with full traceback rather than silently converting them to refusals.

### Risk 5

- **Title**: Trace ID cross-validation is string-equality only, no provenance chain
- **Location**: `spectrum_systems/modules/runtime/next_governed_cycle_runner.py:140-141`
- **Description**: The runner checks `next_cycle_decision.trace_id == next_cycle_input_bundle.trace_id`. This verifies co-origin but does not verify that the trace ID is actually valid, was produced by the previous cycle, or chains to an existing trace lineage. A caller can supply matching but fabricated trace IDs.
- **Why it matters**: Trace integrity is the foundation of replay and audit. Without provenance validation, a caller can inject a synthetic decision+bundle pair with a plausible trace ID and bypass the governed chain.
- **Minimal fix**: Add a `source_cycle_runner_result_ref` field to `next_cycle_input_bundle` that must match a previously emitted `cycle_runner_result_id`. Validate this ref in the runner before execution.

---

## Determinism Risks

- **Timestamp fallback**: When `created_at` is `None`, `_utc_now()` introduces wall-clock dependency. All downstream hashes that include `created_at` become nondeterministic. (Risk 2 above.)
- **Sort stability**: `sorted(set(...))` is used throughout for deduplication. This is deterministic for strings but would break for mixed types. Currently safe since all inputs are string-coerced, but no type guard enforces this invariant.
- **`pqx_execute_fn` opaqueness**: The injected execution function is a black box. Its return value is trusted without schema validation inside `run_next_governed_cycle`. If the function returns nondeterministic results, the entire result chain becomes nondeterministic.

## Governance Risks

- **Control bypass via direct call**: `run_system_cycle` can be called directly (bypassing `run_next_governed_cycle`) without decision/bundle gating. There is no enforcement that execution must flow through the governed runner.
- **Program enforcement gap**: `decide_next_cycle` (system_cycle_operator.py:547-631) checks program alignment, drift, and failure thresholds but does not validate that the program artifact itself is schema-valid or current. A stale or malformed program artifact produces a valid decision.
- **No authorization re-validation**: `run_next_governed_cycle` validates the decision and bundle but does not re-validate `authorization_signals` against the current system state. The authorization signals passed in may be stale relative to the actual control plane state.

## Boundedness Risks

- **Single-call bounded, multi-call unbounded**: The function executes at most one cycle per invocation. But the emitted `next_cycle_decision_ref` and `next_cycle_input_bundle_ref` are designed to be consumed by the next invocation, creating an implicit chain with no depth limit. (Risk 1 above.)
- **No timeout or resource budget**: The runner has no execution timeout. If `run_system_cycle` (the inner execution) hangs, the runner hangs indefinitely.
- **`execution_policy` not validated**: The `execution_policy` parameter is passed through to `run_system_cycle` without schema validation. A malformed policy (e.g., `max_batches_per_run: 999`) could cause the inner cycle to execute far more batches than intended.

## Replay / Trace Risks

- **Trace ID is opaque string**: No schema enforces that `trace_id` references a real trace lineage record. The `^trace-[A-Za-z0-9._:-]+$` pattern is permissive.
- **No replay entry point in `cycle_runner_result`**: The result contains `emitted_artifact_refs` but no structured replay entry point (unlike the `system_cycle_operator` which emits `replay_entry_points`). An auditor cannot deterministically reconstruct the input state from the result alone.
- **`bundle_consumption_summary` is not schema-validated**: The third field in the return dict (`bundle_consumption_summary`) is emitted but not validated against any schema, creating an uncontracted surface.

## Operator Risks

- **Refusal reason codes lack severity ranking**: The `refusal_reason_codes` array is flat. An operator seeing `["decision_stop", "input_bundle_invalid"]` cannot tell which reason is primary or whether the stop was intentional vs. erroneous.
- **No escalation channel in the runner**: When `decision=escalate`, the runner refuses with `decision_escalate` but has no mechanism to notify an operator or trigger an escalation workflow. The escalation is recorded but not acted upon.
- **CLI exit codes are coarse**: `run_next_governed_cycle.py` returns 0 (executed), 1 (refused/failed), or 2 (crash). There is no distinction between "refused because decision=stop" (expected) and "refused because trace_mismatch" (unexpected).

---

## Recommended Follow-Up Actions

1. **Add `continuation_depth` to `next_cycle_input_bundle`** and enforce `max_continuation_depth` in the runner. Schema change + 3-line code change. Blocks unbounded chaining.

2. **Make `created_at` mandatory** in `run_next_governed_cycle` (remove `None` default). Update CLI and tests to always supply it. Eliminates timestamp nondeterminism.

3. **Separate `required_reviews` from `unresolved_blockers`** in `_build_next_cycle_input_bundle`. Only blocking reviews populate `unresolved_blockers`. Prevents false refusals.

4. **Add `error_detail` field to `cycle_runner_result` schema** and stop embedding error strings in `emitted_artifact_refs`. Narrow the except clause to `SystemCycleOperatorError`.

5. **Add `source_cycle_runner_result_ref` to `next_cycle_input_bundle`** for provenance chain validation. Blocks synthetic decision+bundle injection.

6. **Schema-validate `execution_policy`** before passing it to `run_system_cycle`. Add a `execution_policy.schema.json` contract.

7. **Emit structured `replay_entry_point`** in `cycle_runner_result` to enable deterministic reconstruction from result alone.

---

## Governance Compliance

- **Execution/eval/control role separation**: The runner (execution) delegates to `run_system_cycle` which internally invokes eval and control layers. The runner does not bypass eval or control. **PASS**.
- **Control bypass check**: Direct calls to `run_system_cycle` bypass the governed runner's decision gating. **WARNING** - not a blocking finding since the runner is the recommended entry point, but no enforcement prevents bypass.
- **Strategy drift check**: Not applicable at this layer; strategy compliance is checked in `cycle_runner.py` at manifest level.
- **Source drift check**: Not applicable at this layer.
- **Schema bypass check**: All three contracts (`next_cycle_decision`, `next_cycle_input_bundle`, `cycle_runner_result`) use `additionalProperties: false` and have required field lists. **PASS**.
- **Certification bypass check**: The runner does not interact with certification directly. Certification is handled in the inner `run_system_cycle` -> `cycle_runner.py` path. **PASS**.
