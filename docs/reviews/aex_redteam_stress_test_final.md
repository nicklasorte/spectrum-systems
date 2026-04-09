# AEX Red-Team Stress Test (Final) — 2026-04-09

## 1. Executive Verdict
- **Boundary is still soft.**
- **Bypass can happen today.**
- **BLOCKER:** AEX is not the only practical ingress to PQX execution for work that can mutate repository state. Direct `run_pqx_slice(...)` callers remain allowlisted and can execute without `build_admission_record`, `normalized_execution_request`, or `tlc_handoff_record`.

## 2. Verification of Previous Fixes
- **execution_ready bypass: CLOSED (for the cycle_runner → handoff path).**
  - `cycle_runner` now routes `execution_ready` through `handoff_to_pqx(...)`.
  - `handoff_to_pqx(...)` enforces repo-write lineage via `_require_repo_write_admission_lineage(...)`.
  - If repo-write is declared and lineage artifacts are missing/invalid, handoff fails closed.
  - Behavior tests confirm block-on-missing lineage and success-on-valid lineage.

- **fix_roadmap_ready bypass: CLOSED (for fix re-entry payload construction in cycle_runner).**
  - `_build_fix_request(...)` now propagates repo-mutation intent and forwards lineage artifacts into fix re-entry payloads when repo-write is inferred or declared.
  - Fix re-entry now blocks when lineage is removed and succeeds when lineage is present.

- **Evidence used:**
  - `spectrum_systems/orchestration/cycle_runner.py` (`execution_ready`, `fix_roadmap_ready`, `_build_fix_request`).
  - `spectrum_systems/orchestration/pqx_handoff_adapter.py` (repo-write lineage enforcement before `run_pqx_slice`).
  - `spectrum_systems/modules/runtime/repo_write_lineage_guard.py` (cross-artifact invariants).
  - `tests/test_cycle_runner.py` and `tests/test_pqx_handoff_adapter.py` (behavior checks).

## 3. Highest-Risk Failure Paths

### 3.1 Direct PQX invocation remains a live alternate ingress
- **Severity:** BLOCKER
- **Files:**
  - `scripts/pqx_runner.py`
  - `spectrum_systems/modules/pqx_backbone.py`
  - `spectrum_systems/modules/runtime/codex_to_pqx_task_wrapper.py`
  - `spectrum_systems/modules/runtime/pqx_bundle_orchestrator.py`
  - `spectrum_systems/modules/runtime/pqx_sequence_runner.py`
  - `tests/test_aex_repo_write_boundary_structural.py`
- **Exact scenario:**
  1. Engineer/operator invokes an allowlisted caller that directly executes `run_pqx_slice(...)`.
  2. Caller does not require `build_admission_record`, `normalized_execution_request`, `tlc_handoff_record`.
  3. Structural test passes because these callers are explicitly allowlisted.
  4. PQX execution proceeds outside AEX/TLC lineage boundary.
- **Why this is a blocker:** Architecture contract says AEX is the only repo-write ingress. Current code preserves multiple non-AEX ingress points.

### 3.2 Guard activation still depends on declared mutation intent at adapter seam
- **Severity:** HIGH
- **Files:**
  - `spectrum_systems/orchestration/pqx_handoff_adapter.py`
- **Exact scenario:**
  1. A caller emits payload with no explicit `repo_mutation_requested` and no admission artifacts.
  2. `_is_repo_mutation_requested(...)` raises `repo_mutation_intent_unknown` (fail-closed in adapter), which is good.
  3. But this only protects paths that actually go through the adapter.
  4. Direct `run_pqx_slice` paths bypass the adapter entirely.
- **Drift risk:** Teams may treat this adapter guard as “global enforcement” when it is only local enforcement.

### 3.3 Structural guard enforces caller allowlist, not invariant compliance per caller
- **Severity:** HIGH
- **Files:**
  - `tests/test_aex_repo_write_boundary_structural.py`
- **Exact scenario:**
  1. Existing allowlisted caller evolves and starts handling more repo-mutating cases.
  2. No test requires that caller to enforce AEX/TLC lineage.
  3. Boundary drifts while structural tests remain green.

## 4. Fail-Closed Assessment
- **Strong where enforced:**
  - AEX rejects malformed/ambiguous requests.
  - TLC rejects repo-write without valid admission lineage.
  - Handoff adapter blocks unknown mutation intent and invalid lineage.
  - Repo-write lineage guard validates schema + cross-artifact trace/request/reference continuity.
- **Fail-open exposure remains at system boundary level:**
  - Any path that directly calls `run_pqx_slice(...)` avoids all AEX/TLC lineage checks by construction.

## 5. Role-Boundary Assessment
- **AEX role:** Correctly scoped to admission artifacts and rejection artifacts.
- **TLC role:** Correctly scoped to orchestration and handoff formalization.
- **PQX adapter role:** Correct local enforcement.
- **Role collapse issue:** System still permits repo-capable execution paths that do not traverse AEX/TLC at all. This is boundary fragmentation, not pure logic bug.

## 6. Trace / Lineage Assessment
- **TLC path:** Reconstructable lineage exists (`build_admission_record` → `normalized_execution_request` → `tlc_handoff_record` with cross-checks).
- **Direct caller path:** No enforced admission lineage chain before execution.
- **Result:** End-to-end lineage is contingent on entrypoint choice, not globally mandatory.

## 7. Schema / Contract Assessment
- Schemas for `build_admission_record`, `normalized_execution_request`, `admission_rejection_record`, and `tlc_handoff_record` are strict (`additionalProperties: false`, required fields present).
- Runtime lineage guard enforces more than schema shape (trace/request/ref continuity), which is correct.
- **Mismatch risk:** Schema rigor is irrelevant when execution path never requires these artifacts.

## 8. Test Coverage Assessment
- **What is covered and passing:**
  - `execution_ready` repo-write blocks without lineage.
  - `fix_roadmap_ready` re-entry blocks without lineage and succeeds with lineage.
  - adapter unknown-intent and lineage checks fail closed.
  - TLC repo-write admission checks fail closed.
- **Gap:**
  - No invariant test states: “any callable path that can produce repo-mutating PQX execution must require AEX/TLC lineage.”
  - Structural allowlist currently codifies multiple direct `run_pqx_slice` callers as acceptable.

## 9. Drift Forecast
- **Most likely future bypass:** convenience wrapper or script extension around an already allowlisted direct caller.
- **Convention-dependent seam:** architectural rule “AEX only ingress” is enforced by policy/doc plus partial tests, not by a single mandatory technical choke-point.
- **What breaks first under normal evolution:** allowlisted direct callers gain new execution modes faster than lineage invariants are propagated.

## 10. Required Fixes
1. **Collapse repo-write execution ingress to one mandatory boundary check (minimal, real):**
   - Add a mandatory repo-write admission guard at the callable edge used by all execution paths (preferred: enforce inside `run_pqx_slice` or an immediately-required wrapper).
   - If execution class/intent is repo-write or unknown for governed paths, require valid lineage artifacts; otherwise fail closed.

2. **Tighten structural policy to remove sanctioned bypasses:**
   - Update `test_aex_repo_write_boundary_structural.py` allowlist so direct `run_pqx_slice` invocation is only allowed through the single enforced ingress seam.
   - Existing alternate callers must route through that seam.

3. **Add one invariant test that survives refactors:**
   - “Repo-write-capable PQX execution cannot proceed without `build_admission_record` + `normalized_execution_request` + `tlc_handoff_record`.”
   - Execute this against each public entrypoint (CLI/module adapter/orchestrator).

## 11. Final Recommendation
- **DO NOT MOVE ON**

Required explicit answers:
1. **Is AEX now the ONLY enforceable repo-write ingress?** No.
2. **Are BOTH previous bypasses (execution_ready + fix_roadmap_ready) fully closed?** Yes, in `cycle_runner` path.
3. **What is the most plausible remaining bypass?** Any allowlisted direct caller invoking `run_pqx_slice(...)` without AEX/TLC lineage.
4. **Which guard is strongest?** `validate_repo_write_lineage(...)` in `repo_write_lineage_guard.py`.
5. **Which guard is weakest?** Repository-level structural allowlist policy for direct `run_pqx_slice` callers.
6. **What invariant still depends on convention?** “All repo-mutating Codex execution must enter through AEX.”
7. **If one test is removed, what failure becomes most likely?** Remove `test_only_approved_callers_invoke_run_pqx_slice_directly` and silent growth of unauthorized direct PQX entrypoints becomes immediate.
8. **Is AEX ‘done for now’?** No.
