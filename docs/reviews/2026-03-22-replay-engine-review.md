# Replay Engine Architecture Review

## 1. Review Metadata
- **Review Date:** 2026-03-22
- **Repository:** spectrum-systems
- **Reviewer:** Claude (Reasoning Agent — Opus 4.6)
- **Inputs Consulted:**
  - `spectrum_systems/modules/runtime/replay_engine.py`
  - `contracts/schemas/replay_result.schema.json`
  - `tests/test_replay_engine.py`

## 2. Scope
- **In-bounds:** BAG replay engine (`run_replay`), replay result schema contract, replay engine test suite. Focused on canonical path integrity, determinism, comparison correctness, fail-closed behavior, contract compliance, and test coverage.
- **Out-of-bounds:** BP legacy replay path (`execute_replay`, `replay_run`), drift detection engine internals, control loop internals, enforcement engine internals, all other modules.

## 3. Executive Summary
- The BAG replay path (`run_replay`) correctly uses the canonical `run_control_loop` -> `enforce_control_decision` path with no bypass or shortcut.
- Replay IDs are deterministic via `uuid5` seeding; input immutability is enforced via `deepcopy`.
- Comparison targets only stable fields (`enforcement_action`, `final_status`).
- **One critical contract violation:** `drift_result` is appended to the replay result after schema validation, violating `additionalProperties: false` in the schema.
- **One high-severity fail-closed violation:** the broad `except Exception` handler in `run_replay` silently returns a result instead of raising, masking canonical-path failures.
- Test coverage is strong for the happy path and mismatch cases but missing for the indeterminate/exception path and type-guard edge cases.

## 4. Maturity Assessment
- **Current Level:** 3/5 — Governed (partial)
- **Evidence:** Schema validation is enforced, canonical path is correct, determinism is achieved for replay IDs and comparisons.
- **Unmet Criteria:** Contract compliance is broken by post-validation mutation; fail-closed is incomplete in the exception handler; indeterminate path is untested.
- **Next-Level Blockers:** Fix the schema contract violation and exception handler behavior; add indeterminate path tests.

## 5. Strengths
- `run_replay` strictly calls `run_control_loop` -> `enforce_control_decision` — no alternate paths.
- `_stable_replay_id` produces deterministic replay IDs via `uuid5`.
- All inputs are `deepcopy`'d before use; test verifies no mutation.
- `_classify_consistency` compares only `enforcement_action` and `final_status` — stable, deterministic fields.
- Schema validation via `_build_replay_result` is performed before returning.
- Input validation raises `ReplayEngineError` for all four input parameters with explicit error codes.
- Governed artifact validation checks artifact against its own schema before replay proceeds.

## 6. Structural Gaps
- **SG-1:** No mechanism prevents callers from re-validating the returned result (which would fail due to `drift_result`).
- **SG-2:** The indeterminate fallback path constructs a result using original decision/enforcement values as defaults — this could produce misleading comparison outcomes.

## 7. Risk Areas
- **RA-1 (Critical):** Post-validation mutation of replay result with `drift_result` field breaks schema contract. Any downstream consumer that validates the result will reject it.
- **RA-2 (High):** Silent exception absorption in `run_replay` lines 950-974 means canonical-path failures are masked. A broken `run_control_loop` or `enforce_control_decision` would not propagate errors to callers.
- **RA-3 (Medium):** Indeterminate path is entirely untested — the most failure-prone code path has zero test coverage.
- **RA-4 (Low):** Type-guard checks (lines 894-901) have no dedicated tests.

## 8. Recommendations
1. **Fix schema contract for `drift_result`** (addresses RA-1): Either add `drift_result` as an optional property in `replay_result.schema.json`, or return a wrapper envelope `{"replay_result": result, "drift_result": drift}` so the validated artifact is not mutated post-validation. The schema approach is simpler if `drift_result` is considered part of the replay result contract.
2. **Remove or restrict the broad exception handler** (addresses RA-2): Replace `except Exception` at line 950 with a raised `ReplayEngineError` wrapping the original exception. If structured indeterminate records are needed, the caller should catch `ReplayEngineError` and build them — the engine itself should fail closed.
3. **Add indeterminate path test** (addresses RA-3): Monkeypatch `run_control_loop` to raise `RuntimeError` and assert the expected behavior (error raised after fix #2, or structured indeterminate record if current behavior is kept).
4. **Add type-guard edge case tests** (addresses RA-4): Parametrize tests passing `None`, `"string"`, and `42` for each of the four `run_replay` inputs.

## 9. Priority Classification
| Recommendation | Priority | Rationale |
|---|---|---|
| Fix schema contract for `drift_result` | **Critical** | Returned artifact violates its own contract; blocks any downstream validation |
| Remove broad exception handler | **High** | Violates fail-closed system invariant; could mask production failures |
| Add indeterminate path test | **Medium** | Coverage gap on the most error-prone path |
| Add type-guard tests | **Low** | Guards are straightforward; low regression risk |

## 10. Extracted Action Items
1. **[CR-1]** Update `replay_result.schema.json` to include optional `drift_result` property (or restructure return value as envelope). Owner: TBD. Artifact: updated schema + passing validation round-trip test. Acceptance: returned replay result passes schema validation including `drift_result`.
2. **[HI-1]** Replace `except Exception` fallback in `run_replay` with raised `ReplayEngineError`. Owner: TBD. Artifact: updated `replay_engine.py`. Acceptance: unexpected exceptions in canonical path propagate to caller.
3. **[MI-1]** Add test for indeterminate/exception replay path. Owner: TBD. Artifact: new test in `test_replay_engine.py`. Acceptance: test covers `run_control_loop` failure scenario.
4. **[LI-1]** Add parametrized type-guard tests for `run_replay` inputs. Owner: TBD. Artifact: new tests in `test_replay_engine.py`. Acceptance: `None`, string, and int inputs all raise `ReplayEngineError`.

## 11. Blocking Items
- **CR-1** blocks any workflow that re-validates replay results downstream (e.g., replay result ingestion into audit stores, drift analysis pipelines).

## 12. Deferred Items
- Review of BP legacy replay paths (`execute_replay`, `replay_run`) — trigger: when legacy paths are scheduled for deprecation or refactoring.
