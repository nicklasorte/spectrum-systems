# AEX Red-Team Stress Test — 2026-04-08

## 1. Executive Verdict

**AEX is a soft boundary.**

AEX enforces well within its own scope. The admission engine is deterministic, fail-closed, and the cross-artifact lineage guard (`validate_repo_write_lineage`) is strong. However, AEX is not the only enforceable repo-write ingress into the system. A parallel orchestration path — `cycle_runner` → `pqx_handoff_adapter` → `run_pqx_slice` — executes PQX work without touching AEX, TLC, or the lineage guard, and is actively wired in production code.

**Can bypass happen today?** Yes. `cycle_runner.run_cycle()` reaches repo-mutating PQX execution via `handoff_to_pqx()` → `run_pqx_slice()` at two state transitions (`execution_ready` and `fix_roadmap_ready`) with no admission check, no lineage validation, and no TLC orchestration. `run_pqx_slice` has zero AEX-related checks.

**Safe to move on?** No. One hardening slice is required to close the cycle_runner bypass before AEX can be described as the enforced ingress boundary.

---

## 2. Highest-Risk Failure Paths

### 2.1 cycle_runner → pqx_handoff_adapter → run_pqx_slice bypasses the entire AEX chain

**Severity: BLOCKER**

**Files involved:**
- `spectrum_systems/orchestration/cycle_runner.py:726,875`
- `spectrum_systems/orchestration/pqx_handoff_adapter.py:42`
- `spectrum_systems/modules/runtime/pqx_slice_runner.py` (no AEX references at all)

**Exact failure scenario:**
`cycle_runner.run_cycle()` enters the `execution_ready` state (line 718), reads a `pqx_execution_request_path` from the cycle manifest, and calls `handoff_to_pqx()` directly. `handoff_to_pqx()` calls `run_pqx_slice()` with the request fields. `run_pqx_slice()` contains zero references to `admission`, `AEX`, `repo_write_lineage`, or `build_admission_record`. The same pattern repeats at the `fix_roadmap_ready` state (line 860) for fix re-entry execution.

**Why it matters:**
This is not an edge path. It is the primary execution path for the autonomous execution loop, documented in `docs/architecture/autonomous_execution_loop.md` and `docs/runbooks/cycle_runner.md`. Any work routed through the cycle runner — including repo-mutating fix execution — executes outside the AEX boundary with no audit trail connecting the PQX execution to any admission decision.

**What currently stops it:**
Nothing. The path is functional, tested, and actively used.

---

### 2.2 Structural boundary test scans only `execute_sequence_run` — misses `run_pqx_slice` callers

**Severity: BLOCKER (test gap enabling 2.1)**

**Files involved:**
- `tests/test_aex_repo_write_boundary_structural.py:35-53`

**Exact failure scenario:**
`APPROVED_REPO_WRITE_CALLERS` is defined as `{"spectrum_systems/modules/runtime/top_level_conductor.py"}`. The test walks the AST looking for calls to `execute_sequence_run(execution_class="repo_write")`. `cycle_runner` never calls `execute_sequence_run` — it calls `run_pqx_slice` via `handoff_to_pqx`. The structural test passes with zero violations while a live bypass exists.

**Why it matters:**
This is the test that was supposed to catch unauthorized repo_write execution paths. It enforces the wrong abstraction level (sequence_runner) while the actual bypass operates one layer below (slice_runner). Any future caller that also bypasses `execute_sequence_run` will be invisible to this test.

**What currently stops it:**
Nothing. The test passes cleanly today while the bypass is live.

---

### 2.3 `_is_repo_mutation_requested()` falls through to `False` — makes TLC admission gate bypassable by omission

**Severity: HIGH**

**Files involved:**
- `spectrum_systems/modules/runtime/top_level_conductor.py:54-63,73-74`

**Exact failure scenario:**
```python
def _is_repo_mutation_requested(run_request: dict[str, Any]) -> bool:
    if isinstance(run_request.get("repo_mutation_requested"), bool):
        return bool(run_request["repo_mutation_requested"])
    admission = run_request.get("build_admission_record")
    if isinstance(admission, dict):
        return str(admission.get("execution_type") or "") == "repo_write"
    normalized = run_request.get("normalized_execution_request")
    if isinstance(normalized, dict):
        return bool(normalized.get("repo_mutation_requested"))
    return False  # line 63 — silent fallback
```
If a caller constructs a TLC run request that is missing the `repo_mutation_requested` boolean AND omits `build_admission_record` AND omits `normalized_execution_request` — all three — the function returns `False` at line 63. `_require_repo_write_admission()` then returns `None` at line 74, and the entire admission gate is silently skipped. No exception is raised. No warning is emitted.

**Why it matters:**
A rushed engineer, a new subsystem adapter, or a script that builds a TLC request manually but doesn't understand the AEX contract will produce exactly this state. The admission gate is convention-dependent: it activates only when the caller correctly populates at least one of the three indicator sources. The gate does not activate by default for unknown input.

**What currently stops it:**
A caller that intends a repo_write but omits all three sources still needs to be able to reach TLC with a `branch_ref` and `objective`. In practice this is low friction. The guard at `_real_pqx` line 491 adds a secondary check but only fires if `repo_mutation_requested` is truthy — which it won't be if source (1) is missing.

---

### 2.4 Duplicate, divergent repo_write guard inside `_real_pqx()` creates role collapse

**Severity: HIGH**

**Files involved:**
- `spectrum_systems/modules/runtime/top_level_conductor.py:489-492`

**Exact failure scenario:**
```python
def _real_pqx(payload: dict[str, Any]) -> dict[str, Any]:
    repo_write_lineage = payload.get("repo_write_lineage") if isinstance(payload.get("repo_write_lineage"), dict) else {}
    if bool(payload.get("repo_mutation_requested")) and not isinstance(payload.get("build_admission_record"), dict):
        raise TopLevelConductorError("direct_pqx_repo_write_forbidden: missing build_admission_record")
```
This is a second, weaker admission check operating inside TLC's internal PQX runner, distinct from the main gate at `_require_repo_write_admission()`. It fires on different inputs (`payload` rather than `run_request`), checks only `build_admission_record`, and does not call `validate_repo_write_lineage()`. The two checks can and will drift: when `_require_repo_write_admission` is updated, `_real_pqx` will not be.

**Why it matters:**
Duplicate enforcement logic at different layers with different inputs is how invariants erode. The weaker duplicate will survive a refactor that removes the stronger one, or will be silently weakened when someone adds a new case without updating both. There is no comment explaining why both exist.

**What currently stops it:**
Both checks happen to enforce the same semantic today. This is convention, not architecture.

---

## 3. Fail-Closed Assessment

**Where fail-closed is strong:**
- `validate_repo_write_lineage()` in `repo_write_lineage_guard.py` is the strongest guard in the system. It requires all three artifacts, cross-validates every ID and reference, and raises on any mismatch with a distinct error code per failure mode. No fallback. No optional fields. Called from both TLC (line 81-88) and PQX sequence runner (line 1091-1098) when `execution_class="repo_write"` is set.
- AEX engine `admit_codex_request()`: missing required fields, non-Mapping input, and ambiguous prompts with target_paths all fail closed with explicit rejection records.
- `tlc_handoff_record` schema: `entry_boundary` is an enum with a single allowed value (`"aex_to_tlc"`); `handoff_status` is an enum; `execution_type` is an enum. Schema validation blocks invalid values before runtime logic runs.

**Where fail-closed is weak:**
- `_is_repo_mutation_requested()` falls through to `False` on missing inputs. The admission gate is not fail-closed — it is fail-open when all three mutation sources are absent.
- `execute_sequence_run()` is fail-closed for `execution_class="repo_write"`, but `cycle_runner` bypasses this entirely by calling `run_pqx_slice()` directly. The fail-closed mechanism only activates when callers choose to invoke it.

**Fail-open tendencies:**
- TLC admission gate skips silently on absent mutation indicators (finding 2.3).
- The cycle_runner path has no admission gate at all (finding 2.1).
- `enforce_dependency_admission=False` is hardcoded at `top_level_conductor.py:545` when TLC invokes `execute_sequence_run`. This disables a secondary admission layer within PQX for TLC-originated execution.

---

## 4. Role-Boundary Assessment

**AEX vs TLC:**
Clean separation. AEX performs admission; TLC requires AEX artifacts before orchestrating repo-write work. Neither module imports from the other in a circular way. The boundary is maintained by contract (TLC expects `build_admission_record` and `normalized_execution_request` as inputs, not by calling AEX internally).

**TLC vs TPA:**
TPA is invoked post-PQX in TLC's state machine (line 1147), not pre-PQX. The `tlc_handoff_record.lineage.intended_path` documents `["TLC", "TPA", "PQX"]` — but actual execution order is TLC → PQX → TPA. The schema allows any order of these three values. This is a low-severity mismatch but it misleads future maintainers about when TPA policy decisions apply.

**TLC/PQX boundary:**
Mostly sound for the TLC → `execute_sequence_run` path. Broken for the cycle_runner → `run_pqx_slice` path.

**Role duplication / collapse:**
- `_real_pqx()` in TLC does partial admission checking that belongs to AEX/lineage guard. Two enforcement sites for the same invariant.
- TLC's `_build_tlc_handoff_record()` builds the TLC handoff record inline rather than delegating to a handoff builder — this is appropriate, but the construction of lineage refs from empty strings (when admission inputs are None) means a schema-invalid handoff could be attempted silently if the `repo_mutation_requested and has_admission_inputs` guard at line 1062 is weakened.

---

## 5. Trace / Lineage Stress Assessment

**Can the path be reconstructed end-to-end?**
For the TLC path: yes. `validate_repo_write_lineage()` enforces continuity of `trace_id` across `build_admission_record`, `normalized_execution_request`, and `tlc_handoff_record`. `request_id` is cross-validated. The `normalized_execution_request_ref` format is deterministic and verified.

For the cycle_runner path: no. `handoff_to_pqx()` generates an `execution_report_artifact` with `artifact_id`, `cycle_id`, and `run_id`, but there is no `trace_id` threading and no lineage back to any admission decision. Replay of a cycle_runner execution cannot establish who authorized it or why.

**What is still implicit:**
- The assertion that cycle_runner PQX executions are safe because they are "governed by cycle manifest approval" — this is not enforced by any artifact check or lineage guard. It is convention.
- The `enforce_dependency_admission=False` flag in TLC's PQX call: the assumption that this is safe is undocumented.

**What would break replay/debugging:**
- All AEX rejection records carry `"created_at": "2026-04-08T00:00:00Z"` — a literal date hardcoded in `spectrum_systems/aex/engine.py:106`. Rejected requests cannot be temporally located in audit history. This date was correct on day of commit and will be wrong for all future rejections.
- cycle_runner executions produce no `trace_id` lineage, so cross-referencing a cycle execution to a governing decision is impossible from artifacts alone.

---

## 6. Schema / Contract Stress Assessment

**Contract strictness:**
The four primary schemas are tight. `build_admission_record`, `normalized_execution_request`, `admission_rejection_record`, and `tlc_handoff_record` all use `additionalProperties: false` (verified via structural test at `test_aex_repo_write_boundary_structural.py:16-32`). Enums are used for status fields. Cross-artifact references use deterministic formats verified at runtime.

**Runtime/contract mismatches:**

1. `tlc_handoff_record.lineage.intended_path` = `["TLC", "TPA", "PQX"]` in the produced artifact, but actual execution order is TLC → PQX → TPA. The schema validates item values, not ordering. The contract describes a path that the runtime does not follow.

2. `target_scope.paths` in `build_admission_record` allows an empty array with no `minItems` constraint. An accepted repo_write admission can have zero path scope. The schema makes no distinction between "scope covers specific files" and "scope is unconstrained." Runtime enforcement does not add this constraint either.

3. `intended_path` items are validated against an enum of subsystem names, but order is unconstrained. `["PQX", "TPA", "TLC"]` passes schema validation.

**Drift risk in examples:**
No schema examples were found for the admission artifacts. The absence of normative examples means that schema-conforming payloads used in tests (e.g., `build_admission_record` with `paths: ["x"]`) are the de facto behavioral specification. If the test payloads drift from realistic values, schema mismatch between tests and production becomes invisible.

---

## 7. Test Blind Spots

**What the current tests prove:**
- AEX rejects missing required fields (test_aex_admission.py)
- AEX rejects ambiguous prompts with sensitive target_paths (test_aex_fail_closed.py)
- TLC raises `direct_tlc_repo_write_forbidden` when `repo_mutation_requested=True` but admission artifacts are missing (test_tlc_requires_admission_for_repo_write.py)
- PQX sequence runner raises `direct_pqx_repo_write_forbidden` when `execution_class="repo_write"` but lineage is absent (test_pqx_repo_write_lineage_guard.py)
- No non-approved caller uses `execute_sequence_run(execution_class="repo_write")` (test_aex_repo_write_boundary_structural.py)

**What they do not prove:**
- That cycle_runner (which calls `run_pqx_slice` directly) requires AEX admission before executing
- That `_is_repo_mutation_requested()` falling through to `False` is caught — no test exercises a TLC run_request with all three mutation sources absent
- That `run_pqx_slice` rejects direct invocation for repo-mutating work — it has no such check
- That `handoff_to_pqx` requires or propagates any admission artifact
- That `target_scope.paths = []` is rejected for `execution_type="repo_write"`
- That `intended_path` order in `tlc_handoff_record` is enforced

**The single most dangerous untested scenario:**
A call to `cycle_runner.run_cycle()` that advances to `execution_ready` and invokes `handoff_to_pqx()` with a `pqx_execution_request` targeting governed source files. Today this succeeds with no admission check. No test asserts that it should not, or that it requires AEX artifacts to proceed.

---

## 8. Drift Forecast

**Most likely erosion path:**
The `cycle_runner` bypass deepens. The autonomous execution loop is the active development surface. As new states, fix types, or re-entry paths are added to `cycle_runner`, each new path will call `handoff_to_pqx()` because it is the established pattern in that module. No test will catch the new bypass because the structural test scans the wrong function. AEX's enforced perimeter progressively shrinks to TLC-path-only while actual execution volume increasingly runs through cycle_runner.

**Most likely future shortcut:**
A new subsystem adapter needs to call TLC for a "lightweight" orchestration case. To avoid the overhead of constructing full AEX artifacts, the adapter omits `build_admission_record` and `normalized_execution_request` and doesn't set `repo_mutation_requested`. `_is_repo_mutation_requested()` returns `False`. The adapter author sees no error, concludes the code is correct, and ships it.

**What will rot first if left alone:**
The `APPROVED_REPO_WRITE_CALLERS` allowlist in `test_aex_repo_write_boundary_structural.py`. It will either grow to include new callers who bypass the guard, or it will become stale as TLC is refactored and the original enforcement point moves. Either way, the test provides a false sense of coverage while the actual bypass surface expands.

---

## 9. Required Fixes

### Fix 1: Extend structural boundary test to cover `run_pqx_slice` callers

**Maps to:** Findings 2.1, 2.2

Add `run_pqx_slice` to the structural scan in `test_aex_repo_write_boundary_structural.py`. Define an `APPROVED_PQX_SLICE_CALLERS` set — currently only `pqx_handoff_adapter.py` — and fail the test for any other file that calls `run_pqx_slice` directly. This makes the bypass surface explicit and prevents new callers from being added silently.

This fix does not close the cycle_runner bypass itself, but it makes the current approved exception visible and prevents expansion.

### Fix 2: Add AEX admission check to `handoff_to_pqx()` or `cycle_runner` for repo-mutating executions

**Maps to:** Finding 2.1

Either `handoff_to_pqx()` must reject calls that carry a `pqx_execution_request` targeting governed paths without an accompanying `build_admission_record`, or `cycle_runner` must gate the `execution_ready` transition on the presence of AEX admission artifacts in the cycle manifest. The check must be fail-closed: missing admission = blocked, not skipped.

This is the primary hardening fix. Without it, AEX cannot be described as the enforced repo-write ingress.

### Fix 3: Harden `_is_repo_mutation_requested()` to fail-closed on absent inputs

**Maps to:** Finding 2.3

The fallback to `False` at line 63 should be replaced with an exception or a fail-closed default. If none of the three mutation sources is present, TLC cannot determine mutation intent and must not proceed silently. At minimum: log a structured warning and require explicit `repo_mutation_requested: false` for non-mutating requests rather than inferring it from absence.

### Fix 4: Replace hardcoded `created_at` in `AEXEngine._reject()`

**Maps to:** Finding 5, trace/lineage integrity

`spectrum_systems/aex/engine.py:106` — `"created_at": "2026-04-08T00:00:00Z"` must be replaced with a dynamic timestamp. Rejection records with a fixed past timestamp are permanently wrong from day one of deployment after the commit date. This corrupts audit trail ordering.

### Fix 5: Remove or consolidate the duplicate admission guard in `_real_pqx()`

**Maps to:** Finding 2.4

The guard at `top_level_conductor.py:491-492` either duplicates `_require_repo_write_admission()` (in which case it should be removed to prevent drift) or it enforces something different (in which case that difference needs to be documented and tested explicitly). As written, it is an undocumented, weaker shadow of the main gate.

---

## 10. Final Recommendation

**MOVE ON AFTER ONE FIX BATCH**

The TLC-path AEX enforcement is sound. The lineage guard is strong. The schemas are tight. But AEX is not the only enforceable repo-write ingress while `cycle_runner` routes through `pqx_handoff_adapter` without admission. Fixes 1 and 2 above are the mandatory items. Fixes 3, 4, and 5 are surgical improvements that remove real drift risk but are not blockers to moving on if Fix 2 closes the primary bypass.

Do not move on without closing the cycle_runner path. Every day the bypass is open, it becomes more entrenched as the established pattern for new autonomous execution states.

---

## 11. Proposed Next Prompt

**Title:** AEX admission enforcement for cycle_runner PQX execution paths

**Summary:**
The `cycle_runner` invokes `handoff_to_pqx()` → `run_pqx_slice()` at `execution_ready` and `fix_roadmap_ready` without any AEX admission check, bypassing the TLC-enforced boundary entirely. This prompt should:

1. Add AEX admission artifact presence validation to `handoff_to_pqx()` — if the `pqx_execution_request` payload includes `execution_type: "repo_write"` or targets governed paths, require a `build_admission_record` reference in the cycle manifest.
2. Extend `test_aex_repo_write_boundary_structural.py` to include an `APPROVED_PQX_SLICE_CALLERS` structural scan alongside the existing `execute_sequence_run` scan.
3. Replace the hardcoded `created_at` in `AEXEngine._reject()` with a dynamic timestamp.
4. Remove the duplicate admission guard at `top_level_conductor.py:491-492` and verify the main gate covers all cases it was shadowing.

Scope is surgical: no changes to existing TLC admission path, no schema changes, no new modules.
