# AEX Red-Team Stress Test (Post-Fix) — 2026-04-08

## 1. Executive Verdict

**The boundary is partially hardened. Bypass is still possible today.**

The primary fix (`BATCH-AEX-FIX-01`) closed the `execution_ready` state's cycle_runner path. It added `_require_repo_write_admission_lineage()` to `pqx_handoff_adapter.handoff_to_pqx()`, hardened TLC's `_is_repo_mutation_requested()` to raise instead of silently returning `False`, extended the structural caller allowlist test to include `run_pqx_slice`, and fixed the hardcoded `created_at` in AEX rejection records.

That is real progress. The enforcement logic inside `validate_repo_write_lineage()` is strong, and the TLC→PQX path is now genuinely fail-closed for properly constructed requests.

The fix is incomplete. One of the two original bypass states — `fix_roadmap_ready` — was not closed. The fix request built by `_build_fix_request()` omits all three mutation indicators (`repo_mutation_requested`, `build_admission_record`, `normalized_execution_request`). The handoff adapter's `_is_repo_mutation_requested()` returns `False` for this payload and the lineage check is silently skipped. Fix bundle execution reaches `run_pqx_slice` without AEX admission.

Additionally, four approved `run_pqx_slice` callers other than `pqx_handoff_adapter.py` operate without AEX admission. The structural test guards new callers but blesses five existing ones that carry no admission enforcement.

---

## 2. Verification of Previous Fix

### Was the cycle_runner bypass closed?

**Partially. The `execution_ready` path was closed. The `fix_roadmap_ready` path was not.**

**Evidence for `execution_ready` closure:**

`pqx_handoff_adapter.handoff_to_pqx()` now calls `_require_repo_write_admission_lineage()` before invoking `run_pqx_slice` (`pqx_handoff_adapter.py:85`). When a request carries `repo_mutation_requested: True` or includes a `build_admission_record`/`normalized_execution_request`, this check fires and calls `validate_repo_write_lineage()` from `repo_write_lineage_guard.py`. Schema validation plus cross-artifact ID continuity checks must pass before execution proceeds.

`test_cycle_runner.py:422-430` confirms that a request with `repo_mutation_requested: True` and no admission artifacts produces `"repo-write handoff rejected"` in blocking issues. The `execution_ready` path now blocks.

**Evidence the `fix_roadmap_ready` path was not closed:**

`cycle_runner._build_fix_request()` (`cycle_runner.py:232-271`) constructs a new request payload with exactly these fields:

```python
request_payload: Dict[str, Any] = {
    "step_id": ...,
    "roadmap_path": ...,
    "state_path": state_path,
    "runs_root": ...,
    "pqx_output_text": f"[fix-reentry cycle={cycle_id} bundle={bundle_id}] ...",
    "fix_bundle": bundle,
    "fix_bundle_index": bundle_index,
    "fix_reentry": True,
    "cycle_id": cycle_id,
}
```

No `repo_mutation_requested`. No `build_admission_record`. No `normalized_execution_request`. No `tlc_handoff_record`. These are not copied from `base_request`.

When this payload passes through `handoff_to_pqx()` → `_require_repo_write_admission_lineage()` → `_is_repo_mutation_requested()`:

```python
def _is_repo_mutation_requested(request: Dict[str, Any]) -> bool:
    if isinstance(request.get("repo_mutation_requested"), bool):  # absent → skip
        ...
    admission = request.get("build_admission_record")
    if isinstance(admission, dict):                               # absent → skip
        ...
    normalized = request.get("normalized_execution_request")
    if isinstance(normalized, dict):                              # absent → skip
        ...
    return False                                                  # ← falls through
```

`_is_repo_mutation_requested` returns `False`. `_require_repo_write_admission_lineage` returns without raising. Execution proceeds to `run_pqx_slice` with no admission lineage.

The test `test_cycle_runner_review_to_fix_reentry_happy_path` (`cycle_runner.py:332`) uses `_manifest(tmp_path, state="implementation_reviews_complete")` with `repo_mutation_requested=False` (the default). The test never exercises fix re-entry for a repo-mutating base request. No test currently verifies that fix re-entry blocks when admission lineage is absent.

The original audit explicitly named `fix_roadmap_ready` as one of the two states requiring the fix. That state remains open.

---

## 3. Highest-Risk Failure Paths

### 3.1 Fix re-entry admission bypass — `fix_roadmap_ready` state

**Severity: BLOCKER**

**Files:**
- `spectrum_systems/orchestration/cycle_runner.py:232-271` (`_build_fix_request`)
- `spectrum_systems/orchestration/cycle_runner.py:862-886` (fix re-entry invocation)
- `spectrum_systems/orchestration/pqx_handoff_adapter.py:46-55` (`_is_repo_mutation_requested`)
- `spectrum_systems/orchestration/pqx_handoff_adapter.py:58-77` (`_require_repo_write_admission_lineage`)

**Exact failure scenario:**

A cycle reaches `fix_roadmap_ready`. The original `pqx_execution_request_path` was a repo-write request with valid AEX admission artifacts. `cycle_runner.run_cycle()` calls `_build_fix_request()` for each bundle. `_build_fix_request` constructs a new payload that copies `step_id`, `roadmap_path`, `state_path`, `runs_root`, `pqx_output_text` — but not `repo_mutation_requested`, `build_admission_record`, `normalized_execution_request`, or `tlc_handoff_record`.

`handoff_to_pqx()` loads this payload. `_is_repo_mutation_requested()` finds no mutation indicators and returns `False`. `_require_repo_write_admission_lineage()` returns without raising. `run_pqx_slice()` executes the fix bundle — which is repo-mutating code — with no AEX/TLC lineage recorded anywhere.

Fix bundle execution is the primary code-change surface in the autonomous loop. It is the path most likely to touch governed files. It is the path with no admission trace.

---

### 3.2 `pqx_handoff_adapter._is_repo_mutation_requested()` silently returns `False` on absent indicators

**Severity: HIGH**

**Files:**
- `spectrum_systems/orchestration/pqx_handoff_adapter.py:46-55`

**Exact failure scenario:**

TLC's `_is_repo_mutation_requested()` was hardened in BATCH-AEX-FIX-01 to raise `TopLevelConductorError` when all three mutation sources are absent (`top_level_conductor.py:66-68`). The identical function in `pqx_handoff_adapter.py` was not hardened. It still returns `False`.

This divergence means: any caller that constructs a PQX request without explicitly declaring mutation intent will silently bypass the handoff admission guard, regardless of whether the execution actually mutates the repo. The adapter falls through to `return False` (line 55) with no warning, no error, and no record that the intent check was inconclusive.

This is not just the fix re-entry path. It is the default behavior for any new PQX request that doesn't include one of the three indicator fields. The guard is convention-dependent on callers, not fail-closed by default.

---

### 3.3 `scripts/pqx_runner.py` — approved direct `run_pqx_slice` caller with no AEX admission

**Severity: HIGH**

**Files:**
- `scripts/pqx_runner.py:152-167`
- `tests/test_aex_repo_write_boundary_structural.py:14-20` (`APPROVED_RUN_PQX_SLICE_CALLERS`)

**Exact failure scenario:**

`scripts/pqx_runner.py` calls `run_pqx_slice()` directly after running `evaluate_pqx_execution_policy()` and `enforce_pqx_required_context()`. Neither of these is an AEX admission check. The script accepts `--step-id` and `--pqx-output-file` as arguments. Any engineer can invoke:

```
python scripts/pqx_runner.py --step-id AI-01 --pqx-output-file /path/to/codex_output.txt
```

This executes a PQX roadmap step — potentially repo-mutating — with no `build_admission_record`, no `normalized_execution_request`, no `tlc_handoff_record`, and no lineage connecting the execution to any admission decision.

The structural test at `test_aex_repo_write_boundary_structural.py:14-20` explicitly allows `scripts/pqx_runner.py` as a `run_pqx_slice` caller. This is a deliberately sanctioned bypass. It is not a future risk — it is a present opening.

`pqx_bundle_orchestrator.py` and `codex_to_pqx_task_wrapper.py` carry the same property: they are approved callers of `run_pqx_slice` with no AEX admission enforcement.

---

### 3.4 `APPROVED_RUN_PQX_SLICE_CALLERS` structural test guards new callers but not existing ones

**Severity: MEDIUM**

**Files:**
- `tests/test_aex_repo_write_boundary_structural.py:14-20`

**Exact failure scenario:**

The structural test (`test_only_approved_callers_invoke_run_pqx_slice_directly`) fails if a new file calls `run_pqx_slice` outside the allowlist. It does NOT verify that allowlisted callers enforce AEX admission. The allowlist currently contains five callers other than `pqx_handoff_adapter.py`, none of which enforce AEX admission.

The test enforces CONTAINMENT of who can call the function. It does not enforce that callers actually require admission before proceeding. A new feature author who inherits an existing allowlisted caller and adds a new execution path through it faces zero structural friction.

The allowlist will grow over time as new callers are added. Each addition is one PR away from bypassing AEX permanently.

---

### 3.5 Fix re-entry test coverage blind spot

**Severity: MEDIUM**

**Files:**
- `tests/test_cycle_runner.py:332-364` (`test_cycle_runner_review_to_fix_reentry_happy_path`)

**Exact failure scenario:**

The happy-path fix re-entry test uses `_manifest(tmp_path, state="implementation_reviews_complete")` with `repo_mutation_requested=False` (default). This means:
- The base request has no admission artifacts
- `_build_fix_request` builds a fix request with no mutation indicators
- The admission guard silently returns `False`
- Execution succeeds — but for a non-repo-mutating workload that would not trigger admission anyway

No test currently asserts that fix re-entry blocks when the base request is repo-mutating and lacks admission lineage. If such a test were added, it would fail today, confirming the BLOCKER above.

---

## 4. Fail-Closed Assessment

**Genuinely fail-closed:**
- `validate_repo_write_lineage()` (`repo_write_lineage_guard.py`): raises with a distinct error code per failure mode. All three artifacts required. Every cross-artifact ID and reference validated. No optional fallback behavior. This is the strongest guard in the system and it is wired correctly into both `top_level_conductor.py` and `pqx_handoff_adapter.py`.
- AEX `admit_codex_request()`: missing fields, invalid shape, and ambiguous prompts with sensitive target paths all fail with explicit rejection records. `created_at` is now dynamic.
- TLC `_is_repo_mutation_requested()`: now raises `TopLevelConductorError` when all three mutation sources are absent. This was hardened in BATCH-AEX-FIX-01.
- `pqx_handoff_adapter._require_repo_write_admission_lineage()`: is fail-closed IF `_is_repo_mutation_requested()` returns `True`. If it returns `False` — which it does for all requests without explicit mutation indicators — the check is entirely skipped.

**Fail-open:**
- `pqx_handoff_adapter._is_repo_mutation_requested()`: returns `False` on absent indicators (no raise, no warning). Behavior diverges from TLC's hardened version.
- Fix re-entry path: zero admission enforcement due to absent indicators in `_build_fix_request` output.
- `scripts/pqx_runner.py`, `codex_to_pqx_task_wrapper.run_wrapped_pqx_task()`: call `run_pqx_slice` with no mutation intent check of any kind.
- `run_pqx_slice()` itself: no AEX references. No lineage parameters. Executes whatever is passed in.

---

## 5. Role-Boundary Assessment

**AEX role:** Correct. AEX performs admission only. It does not orchestrate or execute. The boundary between AEX and TLC is clean.

**TLC role:** Largely correct. TLC requires AEX artifacts before orchestrating repo-write work. The `_require_repo_write_admission()` guard fires on the TLC-path. The duplicate, weaker guard in `_real_pqx()` (`top_level_conductor.py:495`) still exists alongside the main gate, creating two enforcement sites that can diverge. This was flagged in the prior audit and remains.

**pqx_handoff_adapter role:** Role collapse is present. The adapter now does partial admission enforcement (via `_require_repo_write_admission_lineage()`), but that enforcement is conditioned on `_is_repo_mutation_requested()` returning True — which it won't for fix re-entry requests. The adapter is doing too little for the cases where intent is absent and not raising when it should.

**cycle_runner role:** cycle_runner is calling the handoff adapter but not ensuring the requests it constructs carry the mutation indicators that the handoff adapter requires to fire. This creates a dependency that is not enforced at the seam: cycle_runner must construct the right payload for the admission guard to activate. It currently does so for `execution_ready` (when `repo_mutation_requested=True` is in the manifest's PQX request) but not for `fix_roadmap_ready`.

---

## 6. Trace / Lineage Assessment

**For the `execution_ready` path (TLC lineage or explicit lineage in PQX request):**
Lineage is now verifiable. `validate_repo_write_lineage()` cross-validates trace IDs, request IDs, and artifact references across all three admission artifacts. A complete audit trail from AEX admission to PQX execution can be reconstructed.

**For the fix re-entry path:**
No lineage. The fix request carries `cycle_id` and a modified `pqx_output_text`, but no `trace_id` threading, no reference to the admission record that authorized the original execution, and no `tlc_handoff_record`. Auditing a fix execution cannot establish who authorized it or which admission decision it inherits.

**For `scripts/pqx_runner.py` and `codex_to_pqx_task_wrapper.py` paths:**
No AEX lineage. PQX executes and produces slice artifacts, but no `build_admission_record` ref is present anywhere in the execution record.

**Trace ID continuity:** The cross-artifact trace ID enforcement in `validate_repo_write_lineage()` is tight. Once it fires, lineage is correct. The problem is it does not fire for three of the seven execution paths in the approved caller list.

---

## 7. Schema / Contract Assessment

**Schema enforcement:** The four core schemas (`build_admission_record`, `normalized_execution_request`, `admission_rejection_record`, `tlc_handoff_record`) use `additionalProperties: false`, enum constraints on status fields, and deterministic reference formats. Schema validation fires via `validate_artifact()` at every admission and handoff point. This layer is sound.

**Runtime/schema mismatches (carried from prior audit, not yet fixed):**

1. `tlc_handoff_record.lineage.intended_path` is documented as `["TLC", "TPA", "PQX"]`, but actual execution order in `_real_pqx()` is TLC → PQX → TPA. The schema does not enforce ordering. This misleads future readers about when TPA policy applies.

2. `build_admission_record.target_scope.paths` allows an empty array. An accepted `repo_write` admission can claim zero path scope. No runtime enforcement adds a `minItems` constraint. This means the admission record does not actually constrain which paths can be mutated.

**Fix request schema gap:** The fix request payload constructed by `_build_fix_request` has no schema. It is an ad-hoc dict that `_validate_request()` in `pqx_handoff_adapter.py:30-34` validates only for the presence of five required string fields (`step_id`, `roadmap_path`, `state_path`, `runs_root`, `pqx_output_text`). There is no enforcement that a fix request must carry admission lineage if it is repo-mutating.

---

## 8. Test Coverage Assessment

**What the post-fix tests now prove:**
- `execution_ready` path blocks when `repo_mutation_requested: True` without admission artifacts (`test_cycle_runner_repo_write_request_fails_closed_without_admission_artifacts`)
- `execution_ready` path succeeds with valid admission lineage (`test_cycle_runner_repo_write_request_succeeds_with_valid_admission_lineage`)
- `handoff_to_pqx` blocks when `repo_mutation_requested: True` without lineage (`test_handoff_to_pqx_repo_write_fails_closed_without_admission_lineage`)
- `handoff_to_pqx` succeeds with valid lineage (`test_handoff_to_pqx_repo_write_succeeds_with_valid_admission_lineage`)
- No new files can be added as `run_pqx_slice` callers without modifying the allowlist (`test_only_approved_callers_invoke_run_pqx_slice_directly`)

**What the tests do NOT prove:**
- That fix re-entry blocks when the base request is repo-mutating and lacks admission lineage
- That `_is_repo_mutation_requested()` in `pqx_handoff_adapter.py` raises or fails closed when all three indicators are absent
- That any of the five non-`pqx_handoff_adapter.py` approved callers enforce AEX admission
- That the `APPROVED_RUN_PQX_SLICE_CALLERS` allowlist cannot grow without admission enforcement being required

**Most dangerous untested scenario:** A `fix_roadmap_ready` cycle transition where `base_request` has `repo_mutation_requested: True` and valid admission artifacts, but the fix request generated by `_build_fix_request` executes without any lineage check. This scenario is structurally guaranteed to succeed today and no test asserts that it should not.

**If one test were removed:** Removing `test_handoff_to_pqx_repo_write_fails_closed_without_admission_lineage` would eliminate the only behavioral guard on the `execution_ready` path. Future callers could pass `repo_mutation_requested: True` without admission artifacts and proceed silently.

---

## 9. Drift Forecast

**Most likely near-term erosion:**

Fix re-entry is the established pattern for bounded re-execution in the autonomous loop. As the loop evolves, new re-execution states and partial-execution paths will follow the same pattern: load base request, build new payload, call `handoff_to_pqx`. None of those new paths will include admission artifacts unless the code explicitly copies them, because the current pattern explicitly does not. The bypass surface will grow with every new re-entry state.

**Most likely shortcut:** An engineer adding a new fix type or partial re-execution mode copies `_build_fix_request` as a template. They see `fix_reentry: True` in the output and assume the cycle governance context (manifest state machine, required reviews) provides sufficient authorization. They don't see an error because `_is_repo_mutation_requested()` returns `False` and the guard is silent. The bypass is invisible.

**Seam most dependent on convention:** The assumption that "fix re-entry is safe because it requires `implementation_reviews_complete` + fix roadmap approval + approved bundle selection" — this governance is real but it is not AEX lineage. No artifact produced during the fix cycle carries a back-reference to an admission decision. The connection between governance and execution is asserted, not traced.

**What will rot first:** `pqx_handoff_adapter._is_repo_mutation_requested()` returning `False` on absent indicators. As more callers construct PQX requests in non-standard ways (fix requests, partial re-execution, emergency paths), more will silently bypass the guard. The divergence from TLC's hardened version of the same function will compound as both functions are independently modified.

---

## 10. Required Fixes

### Fix 1: Forward admission lineage in `_build_fix_request`

**Target:** `spectrum_systems/orchestration/cycle_runner.py:252-271`

When `base_request` contains `repo_mutation_requested: True`, `_build_fix_request` must forward `repo_mutation_requested`, `build_admission_record`, `normalized_execution_request`, and `tlc_handoff_record` into the fix request payload. This is the minimum change required to activate the existing guard at `_require_repo_write_admission_lineage()` for fix re-entry.

No schema changes required. No new enforcement layer required. The guard already exists; the payload just needs to carry the trigger.

### Fix 2: Harden `pqx_handoff_adapter._is_repo_mutation_requested()` to match TLC

**Target:** `spectrum_systems/orchestration/pqx_handoff_adapter.py:46-55`

Replace `return False` with a raise (or default-True behavior) when all three mutation indicators are absent. The function as written diverges from `top_level_conductor._is_repo_mutation_requested()` which raises on absent indicators. Non-mutating callers must set `repo_mutation_requested: False` explicitly; absence must not be treated as negation.

This fix is necessary to make the handoff adapter fail-closed rather than fail-open on unknown intent.

### Fix 3: Add fix re-entry admission enforcement test

**Target:** `tests/test_cycle_runner.py`

Add a test that:
- Constructs a manifest at `fix_roadmap_ready` with a base request where `repo_mutation_requested: True`
- Verifies that `run_cycle` blocks with an admission-related error when the base request lacks admission lineage
- Verifies that `run_cycle` succeeds at `fix_roadmap_ready` when admission lineage is valid and forwarded

Without this test, Fix 1 has no behavioral coverage and can be silently reverted.

---

## 11. Final Recommendation

**DO NOT MOVE ON**

The `fix_roadmap_ready` bypass was explicitly named in the original audit as one of two paths requiring closure. It was not closed. Fix bundle execution — the primary code-change surface in the autonomous execution loop — still reaches `run_pqx_slice` without AEX admission lineage. This is not a future risk or a drift concern. It is an open bypass today.

Fixes 1, 2, and 3 above are surgical and do not require architectural changes. Fix 1 (`_build_fix_request` forwarding) is a one-function change. Fix 2 (raising on absent indicators in `pqx_handoff_adapter`) is a two-line change. Fix 3 is a test. All three are within the scope originally declared for BATCH-AEX-FIX-01.

The TLC enforcement path is sound. The lineage guard is strong. The `execution_ready` path is closed. AEX is one targeted fix batch away from being a genuinely enforced boundary. It is not there yet.
