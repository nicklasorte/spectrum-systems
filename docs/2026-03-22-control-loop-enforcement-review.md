# Control Loop Enforcement Architecture Review
**Date:** 2026-03-22
**Reviewer:** Claude (Reasoning Agent — Sonnet 4.6)
**Scope:** Core control loop and enforcement path only

**Modules reviewed:**
- `spectrum_systems/modules/runtime/control_loop.py`
- `spectrum_systems/modules/runtime/control_integration.py`
- `spectrum_systems/modules/runtime/evaluation_control.py`
- `spectrum_systems/modules/runtime/enforcement_engine.py`
- `spectrum_systems/modules/runtime/replay_engine.py` (BAG)
- `spectrum_systems/modules/runtime/drift_detection_engine.py` (BAH)
- `spectrum_systems/modules/runtime/regression_harness.py` (BAI)

---

## Decision

**CONDITIONAL PASS**

The canonical eval → decision → enforcement path is structurally sound and schema-governed. However, three defects — a fail-open null check in the integration gate, a non-deterministic decision ID, and an active legacy enforcement bypass — individually break the determinism or fail-closed guarantees. All three must be resolved before this loop can be considered production-grade.

---

## Critical Findings (max 5)

**CF-1 — Fail-open null in `control_integration.py:275–276`**
`execution_result.get("execution_status", "blocked")` returns `None` when the key exists with value `None`. `None not in _BLOCKED_STATUSES` evaluates to `True`, setting `continuation_allowed = True`. Any upstream module that returns a partially-populated result dict (e.g., a chain path that sets `"execution_status": None`) silently opens the gate.

**CF-2 — Non-deterministic `decision_id` in `evaluation_control.py:49`**
`_new_id()` uses `uuid.uuid4()` — a random UUID. The same eval_summary inputs produce a different `decision_id` on every call. This breaks replay: the canonical decision artifact cannot be compared deterministically across runs, and the `enforcement_result.input_decision_reference` field references a different ID each time. The `failure_eval_case` path in `control_loop.py` correctly derives a deterministic ID from `run_id`; `evaluation_control.py` must match this pattern.

**CF-3 — Dual active enforcement paths**
`enforcement_engine.py` exposes two enforcement functions: `enforce_control_decision` (canonical BAF path, schema `enforcement_result`) and `enforce_budget_decision` (legacy path, different output schema with `enforcement_id`, `execution_permitted`, `enforcement_status`). `replay_run()` in `replay_engine.py` calls `enforce_budget_decision` directly, bypassing the canonical path. These two paths produce incompatible artifacts with different field semantics and no `fail_closed` flag on the legacy path. There is no single enforcement path.

**CF-4 — `replay_run()` does not reproduce the canonical control chain**
`replay_run()` replays through `validate_and_emit_decision → build_validation_budget_decision → enforce_budget_decision`, which is the legacy budget pathway, not the canonical `eval_summary → evaluation_control_decision → enforcement_result` chain. A replay that uses a different enforcement function cannot validate that the canonical loop is deterministic. Provenance of the original decision is not captured in a way that allows canonical-path replay.

**CF-5 — Dead enforcement artifact `_BYPASS_BLOCKED_RESULT` in `control_integration.py:103–121`**
This dict is defined, fully populated, and named to suggest it is returned on bypass detection — but it is never referenced or returned by any code path. Its existence creates ambiguity: either a bypass-detection path was removed without removing the artifact (orphaned code), or it was intended but never wired in, leaving a latent enforcement gap unclosed.

---

## Required Fixes (blocking)

1. **CF-1 — Harden the null-status gate.**
   Replace the `exec_status not in _BLOCKED_STATUSES` check with a positive-allowlist pattern: `continuation_allowed = (exec_status == "success")`. Any status that is not explicitly `"success"` must deny. The current set-exclusion logic fails open on any unexpected or null status.

2. **CF-2 — Derive a deterministic `decision_id` in `evaluation_control.py`.**
   Replace `uuid.uuid4()` with a stable ID derived from the input signal (e.g., `uuid.uuid5` seeded from `eval_run_id + triggered_signals + schema_version`). The `failure_eval_case` path in `control_loop.py` already demonstrates the correct pattern: `f"ECD-{signal['run_id']}-FAILURE"`.

3. **CF-3 / CF-4 — Eliminate the legacy enforcement path from replay.**
   `replay_run()` must be updated to replay through the canonical `enforce_control_decision` path. The `enforce_budget_decision` function must either be removed or gated behind an explicit deprecation boundary that cannot be reached from any replay or regression flow.

4. **CF-5 — Resolve `_BYPASS_BLOCKED_RESULT`.**
   Either wire it into the enforcement path at the intended detection point, or delete it. Orphaned enforcement artifacts in the integration layer must not remain in the codebase.

---

## Optional Improvements

- **Threshold override governance.** `build_evaluation_control_decision` accepts an optional `thresholds` dict that merges over `DEFAULT_THRESHOLDS`. An unchecked caller can silently relax all thresholds. This parameter should either be removed from the public surface or require an explicit governance token.

- **Open-span replay status.** `_execute_steps()` maps `status=None` (open spans) to `'ok'`. This can cause an originally-in-flight or blocked span to be recorded as successful in replay, masking enforcement failures. Map `None` to `'skipped'` with a determinism note instead.

- **Regression gate `decision_consistency` default.** `evaluate_trace_pass_fail()` defaults `actual_status` to `STATUS_INDETERMINATE` when `decision_consistency` is absent from the analysis artifact. This is safe but should emit a warning rather than silently degrading to indeterminate.

- **Drift ID determinism.** `_build_drift_id()` uses `uuid.uuid5` seeded from `trace_id|baseline_id|replay_run_id` — this is correct. No action required.

---

## Architectural Risk Summary

The primary failure mode under scale is the covert divergence of the two enforcement paths. As the system grows, the legacy `enforce_budget_decision` path will continue to be called by replay and any other consumers that have not been migrated, while the canonical `enforce_control_decision` path evolves independently. Because the two paths produce artifacts with different schemas and different field semantics, automated consistency checks cannot detect the split — each path produces a valid artifact in its own schema, and no cross-path validator exists. Combined with the non-deterministic `decision_id` in `evaluation_control.py`, the regression harness cannot establish that a replayed decision matches the original one: the IDs are different every call, so the comparison surface is undefined. The null-status fail-open gap in `control_integration.py` is the highest-severity acute risk — it is a single upstream mistake away from silently allowing execution that should be blocked. Together, these three defects mean the system has the structural appearance of a governed control loop without the enforcement guarantees that appearance implies.
