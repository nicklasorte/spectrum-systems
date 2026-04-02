# PQX Red-Team Security Audit (Post-MVP 10-Slice Run)

**Date:** 2026-04-02
**Scope:** PQX execution integrity, control loop correctness, trace truth, determinism, dependency enforcement, state handling
**Method:** Code-level red-team analysis of runtime modules
**Constraint:** No architectural redesign; surgical fixes only

---

## Top 5 Vulnerabilities (Ranked by Severity)

---

### V-1: Trace Invariant Bypass on Context-Enforcement Block (Missing Refs Accepted)

**Severity:** BLOCKER

**Location:** `spectrum_systems/modules/runtime/pqx_sequential_loop.py`, `_validate_trace_invariants` (lines 94-142), context-enforcement block path (lines 214-235)

**Exploit scenario:**
A slice fails context enforcement (e.g., missing `authority_evidence_ref`). The loop emits a slice record with `status: "blocked"` and `pqx_execution_artifact_ref: null`, `slice_execution_record_ref: null`, `eval_result_ref: null`, `control_decision_ref: null`. The trace invariant validator at line 104 only checks refs for slices with `status in {"completed", "stopped"}`. A `"blocked"` slice passes validation with all null refs.

**Root cause:** `_validate_trace_invariants` does not enforce ref presence for `status: "blocked"` slices. The schema distinguishes three statuses but the invariant checker only gates two. A blocked slice can appear in the final trace with no verifiable evidence trail.

**Impact:** A trace artifact emitted to downstream consumers contains a slice with `final_slice_status: "BLOCK"` but zero artifact refs. Any audit, replay, or provenance chain that attempts to verify *why* the block occurred will find no linked evidence. The trace misrepresents the system's ability to provide verifiable proof of its own decisions.

**Minimum safe fix:**
In `_validate_trace_invariants`, add a check for `status == "blocked"` slices that requires at least `wrapper_ref` to be present (it is always available since the wrapper is parsed before context enforcement runs):

```python
if status == "blocked":
    if not isinstance(row.get("wrapper_ref"), str) or not row["wrapper_ref"].strip():
        raise PQXSequentialLoopError(
            f"trace invariant failed: blocked slice {slice_id} must retain wrapper_ref"
        )
```

Additionally, the blocked-slice dict at line 214 should populate `enforcement_result.blocking_source` with `"context_enforcement"` so the reason is structurally typed, not just a comma-joined string.

---

### V-2: Fixture-Mode Decision Derived from Path/Text Substring Matching

**Severity:** BLOCKER

**Location:** `spectrum_systems/modules/runtime/pqx_slice_runner.py`, `_resolve_fixture_decision_mode` (lines 387-394)

**Exploit scenario:**
The function determines whether the replay fixture should simulate `allow`, `review`, or `block` by checking whether the `runs_root` path or `pqx_output_text` contains substrings like `"review"` or `"block"`. A legitimate slice whose `pqx_output_text` contains the sentence *"This step does not block further progress"* will match `"block"` and force a deny decision. Conversely, a `runs_root` path like `/data/pqx_runs/reviewed_steps/` will match `"review"` and force a require_review decision.

**Root cause:** Decision-mode selection uses unconstrained substring matching on free-text fields that have no contract requiring them to avoid decision-relevant keywords. This leaks identity/content into decision semantics.

**Impact:** Identical logical inputs produce different control decisions depending on incidental string content in paths or output text. This violates the determinism contract: the same roadmap step with the same eval signals can be allowed or blocked depending on the directory it runs from.

**Minimum safe fix:**
Replace substring heuristic with an explicit `fixture_decision_mode` parameter on `run_pqx_slice`. Default to `"allow"`. The caller (sequential loop or test harness) must declare the mode explicitly. Remove all string-sniffing logic:

```python
def run_pqx_slice(
    *,
    # ... existing params ...
    fixture_decision_mode: str = "allow",  # "allow" | "review" | "block"
) -> dict:
    if fixture_decision_mode not in {"allow", "review", "block"}:
        return _block_payload(step_id=..., run_id=..., reason="invalid fixture_decision_mode")
    # Use fixture_decision_mode directly instead of _resolve_fixture_decision_mode
```

---

### V-3: Non-Deterministic Enforcement ID Due to Timestamp in Hash Input

**Severity:** MEDIUM

**Location:** `spectrum_systems/modules/runtime/enforcement_engine.py`, `enforce_control_decision` (lines 116-133)

**Exploit scenario:**
`enforcement_result_id` is computed via `_deterministic_id("ENF", deterministic_identity_payload)`. The payload at line 116 does not include the timestamp, so the ID itself is deterministic. However, the `enforcement_result` at line 130 includes `"timestamp": _now_iso()` (line 134). If the same decision artifact is enforced twice (e.g., during a retry or replay verification), the two enforcement results will have identical `enforcement_result_id` values but different `timestamp` fields. A downstream deduplication system that hashes the full artifact (not just the ID) will treat them as different artifacts despite being logically identical.

**Root cause:** The enforcement result mixes a deterministic ID with a non-deterministic timestamp field. The artifact's identity and its content diverge.

**Impact:** Cross-run comparison, artifact deduplication, and trace replay verification can produce false drift signals. Two identical enforcement decisions appear as distinct artifacts, potentially triggering `stability_breach` in evaluation_control.

**Minimum safe fix:**
Accept an optional `timestamp` parameter in `enforce_control_decision` with a default of `_now_iso()`. For replay/verification paths, the caller passes the canonical timestamp. For live execution, the default applies:

```python
def enforce_control_decision(decision_artifact: dict, *, timestamp: str | None = None) -> dict:
    # ...
    result = {
        # ...
        "timestamp": timestamp or _now_iso(),
        # ...
    }
```

---

### V-4: Slice Runner Marks Row "complete" Before Sequential Loop Evaluates Enforcement

**Severity:** MEDIUM

**Location:** `spectrum_systems/modules/runtime/pqx_slice_runner.py` line 819; `spectrum_systems/modules/runtime/pqx_sequential_loop.py` lines 296-300, 354-358

**Exploit scenario:**
`run_pqx_slice` unconditionally sets `row_state["status"] = "complete"` and calls `save_state()` at line 819-822 before returning. The sequential loop then builds an `evaluation_control_decision` from the replay artifact (line 287), runs enforcement (line 296), and checks the result (line 354). If enforcement returns `BLOCK` or `REQUIRE_REVIEW`, the loop correctly stops -- but the roadmap row state on disk already says `"complete"`.

On the next run, `resolve_executable_row` at `pqx_backbone.py:205-213` will see `status == "complete"` and skip this row, returning `MISSING_ROW` (already complete). The row will never be re-executed even though the sequential loop determined it should be blocked.

**Root cause:** The slice runner writes completion state to disk as a side effect of successful execution, but the sequential loop's enforcement decision (which can override to BLOCK) happens after this write. State persistence and control decisions are not sequenced correctly.

**Impact:** A row that should be blocked or require review is permanently marked complete. Subsequent runs skip it. The enforcement decision is effectively ignored for state purposes. This is a control bypass.

**Minimum safe fix:**
Do not mark the row as `"complete"` in `run_pqx_slice`. Instead, return the execution record and let the sequential loop (or the caller) mark completion only after enforcement confirms ALLOW. In the slice runner, change line 819 to:

```python
row_state["status"] = "executed_pending_enforcement"
```

And add a new exported function `confirm_row_completion(state_path, step_id)` that the sequential loop calls only on ALLOW. This preserves fail-closed: if the process crashes between execution and enforcement, the row is not marked complete.

---

### V-5: `_derive_run_id` Falls Back to `trace_id`, Creating Circular Identity

**Severity:** LOW

**Location:** `spectrum_systems/modules/runtime/pqx_sequential_loop.py`, `_derive_run_id` (lines 79-91)

**Exploit scenario:**
If `initial_context` has no `run_id` and no slice wrapper contains a `task_identity.run_id`, the function falls back to `trace_id` (line 91). The `trace_id` is itself derived from the slices and initial_context via `_deterministic_trace_id`. The enforcement engine later requires `run_id` to be present and non-empty on the decision artifact (line 109 of enforcement_engine.py). Since `run_id == trace_id`, the enforcement result's identity hash at line 116 conflates trace and run identity, meaning two different logical runs that happen to have the same slice/context inputs will share the same `run_id`, `trace_id`, AND `enforcement_result_id`.

**Root cause:** The fallback creates a circular identity dependency where run_id is derived from trace_id which is derived from inputs. Run identity should be externally provided or fail closed.

**Impact:** Cross-run contamination: two separate invocations with identical inputs produce identical run_ids, making it impossible to distinguish them in audit logs or error-budget windows. The `aggregate_error_budget_window` in control_loop.py would collapse them into a single run.

**Minimum safe fix:**
Fail closed when no explicit `run_id` is available instead of falling back to `trace_id`:

```python
def _derive_run_id(*, context, slices, trace_id):
    raw = context.get("run_id")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    for slice_payload in slices:
        wrapper = slice_payload.get("wrapper")
        if isinstance(wrapper, Mapping):
            identity = wrapper.get("task_identity")
            if isinstance(identity, Mapping):
                run_id = identity.get("run_id")
                if isinstance(run_id, str) and run_id.strip():
                    return run_id.strip()
    raise PQXSequentialLoopError("run_id must be explicitly provided in initial_context or slice wrapper task_identity")
```

---

## Overall System Assessment

**SAFE for production-style execution** -- with caveats.

The two BLOCKERs (V-1 and V-2) must be addressed before the system can be considered audit-grade. V-1 is a trace completeness gap that undermines provenance claims. V-2 is a determinism violation that can produce different decisions from identical logical inputs.

The MEDIUM findings (V-3 and V-4) are correctness risks under retry/replay and multi-slice enforcement scenarios respectively. V-4 is particularly concerning because it creates a state/control divergence that persists across runs.

The LOW finding (V-5) is a defense-in-depth issue that only manifests when callers omit `run_id`, which current usage appears to avoid.

The core control loop (`evaluation_control.py`, `enforcement_engine.py`, `control_loop.py`) is well-constructed:
- Threshold relaxation is correctly blocked
- Budget authority enforcement is sound
- Decision-to-enforcement mapping is deterministic and schema-validated
- Fail-closed semantics are consistently applied at decision boundaries
- Judgment authority can only escalate, never relax

The sequential loop (`pqx_sequential_loop.py`) correctly stops on BLOCK/REQUIRE_REVIEW and carries context forward. The bundle state system (`pqx_bundle_state.py`) has robust ordering enforcement and review-checkpoint gates.

**Blockers for audit-grade status:** V-1, V-2
**Recommended before production use:** V-3, V-4

---

## Confidence Level

**High**

All five vulnerabilities are directly observable in the source code with concrete trigger scenarios. No speculative or theoretical-only findings are included. Each exploit can be reproduced by constructing the described input conditions against the existing codebase.
