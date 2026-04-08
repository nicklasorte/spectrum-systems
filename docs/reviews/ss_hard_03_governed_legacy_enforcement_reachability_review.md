# SS-HARD-03 — Governed vs Legacy Enforcement Reachability Review

**Date:** 2026-04-08
**Branch:** work
**Scope:** Reachability of legacy enforcement seam from governed execution paths
**Method:** Static call-path/code-path audit with targeted repo search
**Verdict:** NOT_SAFE_TO_MERGE

## Question

State the exact question being answered:
“Can any governed execution path still call `enforce_budget_decision(..., compatibility_mode=True)` either directly or indirectly, including through `execute_with_enforcement`?”

## Files Inspected

- `spectrum_systems/modules/runtime/enforcement_engine.py`
- `spectrum_systems/modules/runtime/control_executor.py`
- `spectrum_systems/modules/runtime/control_integration.py`
- `spectrum_systems/modules/runtime/pqx_sequential_loop.py`
- `spectrum_systems/modules/runtime/pqx_slice_runner.py`
- `spectrum_systems/modules/runtime/replay_engine.py`
- `spectrum_systems/modules/runtime/agent_golden_path.py`
- `spectrum_systems/modules/runtime/evaluation_enforcement_bridge.py` (name-collision check for non-target `enforce_budget_decision`)
- `spectrum_systems/modules/runtime/system_enforcement_layer.py`
- `spectrum_systems/modules/runtime/top_level_conductor.py`
- `scripts/run_enforced_execution.py`
- `scripts/run_harness_integrity_bundle.py`
- `tests/test_enforcement_engine.py`
- `tests/test_control_executor.py`
- `tests/test_pqx_sequential_loop.py`
- `tests/test_control_integration.py`
- `tests/test_replay_engine.py`
- `docs/architecture/system_registry.md`

## Call-Path Audit

### 1. Legacy enforcement entrypoints

- Target legacy seam is defined in `spectrum_systems/modules/runtime/enforcement_engine.py`:
  - `def enforce_budget_decision(decision: dict, *, compatibility_mode: bool = False) -> dict`
- Compatibility guard behavior:
  - Raises if `compatibility_mode is not True`.
  - Raises if caller is not on `_LEGACY_CALLER_ALLOWLIST`/test prefixes.
  - `_LEGACY_CALLER_ALLOWLIST` includes `spectrum_systems.modules.runtime.control_executor`.
- Direct invocation is therefore possible from allowed callers, and blocked for most others.

### 2. Canonical enforcement entrypoints

- Canonical entrypoint is defined in `spectrum_systems/modules/runtime/enforcement_engine.py`:
  - `def enforce_control_decision(decision_artifact: dict, *, timestamp: str | None = None) -> dict`
- Governed callers using canonical path:
  - `control_integration.enforce_control_before_execution(...)`
  - `pqx_sequential_loop.run_pqx_sequential(...)`
  - `pqx_slice_runner.confirm_slice_completion_after_enforcement_allow(...)`
  - `replay_engine.replay_run(...)` and replay execution path in `replay_execution_record(...)`
  - `agent_golden_path` enforcement stage

### 3. Callers of `enforce_budget_decision`

Exhaustive call list (repo code, excluding historical docs):

1. `spectrum_systems/modules/runtime/control_executor.py::execute_with_enforcement`
   - Call: `enforce_budget_decision(budget_decision, compatibility_mode=True)`
   - Classification: **governed-risk / compatibility-live runtime path** (legacy seam explicitly permitted in runtime module)
2. `tests/test_enforcement_engine.py`
   - Multiple direct calls for guard/allowlist behavior validation
   - Classification: **test-only**
3. `spectrum_systems/modules/runtime/evaluation_enforcement_bridge.py::enforce_budget_decision`
   - Different function with same name/signature shape (no `compatibility_mode`), not the target seam
   - Classification: **name collision / non-target**

Import-level evidence for target seam (`enforcement_engine.enforce_budget_decision`) shows only:
- `control_executor.py`
- `tests/test_enforcement_engine.py`

### 4. Callers of `execute_with_enforcement`

Exhaustive call list:

1. `scripts/run_enforced_execution.py::main`
   - Direct CLI call to `execute_with_enforcement(args.bundle)`
   - Classification: **non-test runtime entrypoint (legacy compatibility CLI)**
2. `spectrum_systems/modules/runtime/control_executor.py::execute_with_replay`
   - Indirect call via `original_enforcement = execute_with_enforcement(bundle_path)`
   - Classification: **compatibility runtime chaining (legacy seam remains reachable)**
3. `tests/test_control_executor.py`
   - Test references/patching
   - Classification: **test-only**

### 5. Governed path reachability

Reachability result: **YES — governed-adjacent runtime execution can still reach the legacy seam.**

Concrete reachable paths:

- Path A (direct):
  - `scripts/run_enforced_execution.py::main`
  - → `control_executor.execute_with_enforcement(bundle_path)`
  - → `enforcement_engine.enforce_budget_decision(..., compatibility_mode=True)`

- Path B (indirect):
  - `control_executor.execute_with_replay(bundle_path)`
  - → `control_executor.execute_with_enforcement(bundle_path)`
  - → `enforcement_engine.enforce_budget_decision(..., compatibility_mode=True)`

Why this is still live:
- `control_executor` is explicitly allowlisted by `_LEGACY_CALLER_ALLOWLIST`.
- `execute_with_enforcement` hard-codes `compatibility_mode=True`.
- No fail-closed routing barrier exists inside `execute_with_enforcement` to force canonical `enforce_control_decision`.

Therefore, the target legacy seam is not fenced to test-only usage; it remains callable on runtime execution surfaces.

## Findings

### F-1: Legacy seam remains runtime-reachable via `execute_with_enforcement`
- Severity: BLOCKER
- Evidence:
  - `control_executor.execute_with_enforcement` calls `enforce_budget_decision(..., compatibility_mode=True)`.
  - `enforcement_engine` explicitly allowlists `spectrum_systems.modules.runtime.control_executor`.
  - `run_enforced_execution.py` exposes this call path as executable CLI entrypoint.
- Why it matters:
  - A live runtime route can still emit legacy enforcement artifacts/semantics instead of canonical `enforcement_result`, preserving dual-path behavior and violating single-path governed enforcement intent.

### F-2: Indirect legacy reachability remains through replay helper chain
- Severity: HIGH
- Evidence:
  - `control_executor.execute_with_replay` invokes `execute_with_enforcement` before running replay.
- Why it matters:
  - Even when replay surfaces are otherwise canonical, this helper path keeps compatibility seam invocation reachable in the same runtime module.

## Merge Decision

### NOT_SAFE_TO_MERGE
Use this if:
- any governed path reaches the legacy seam
- execute_with_enforcement keeps the legacy seam live on a governed path
- consumer ambiguity remains on governed paths

This condition is met: `execute_with_enforcement` is a live runtime path that still reaches `enforce_budget_decision(..., compatibility_mode=True)`.

## Required Follow-Up (only if NOT_SAFE_TO_MERGE)

1. Remove legacy call from `control_executor.execute_with_enforcement` and migrate it to canonical `enforce_control_decision` flow.
2. Remove `spectrum_systems.modules.runtime.control_executor` from `_LEGACY_CALLER_ALLOWLIST` once migration lands.
3. Add an explicit non-test reachability guard (test or static check) asserting zero runtime callers of `enforcement_engine.enforce_budget_decision`.
4. Retain legacy seam only behind test-only or fully isolated compatibility adapters that are unreachable from governed execution entrypoints.

## Notes

- `evaluation_enforcement_bridge.py` defines a separate `enforce_budget_decision` function that is not the target seam (`compatibility_mode` signature absent), but it can create naming ambiguity during audits.
