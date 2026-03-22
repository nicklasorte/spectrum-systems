# BAE Observe Layer Review — 2026-03-22

---

## Scope

This review is **strictly limited to the OBSERVE layer** of the BAE control loop: the
components responsible for ingesting execution outputs and converting them into
schema-validated `evaluation_monitor_record` and `evaluation_monitor_summary` artifacts.

Files reviewed:

| File | Role |
|---|---|
| `spectrum_systems/modules/runtime/evaluation_monitor.py` | Core OBSERVE implementation (legacy + control-loop paths) |
| `contracts/schemas/evaluation_monitor_record.schema.json` | Record schema |
| `contracts/schemas/evaluation_monitor_summary.schema.json` | Summary schema |
| `contracts/schemas/regression_run_result.schema.json` | Input schema (boundary) |
| `tests/test_evaluation_monitor.py` | Legacy monitor record tests |
| `tests/test_evaluation_control_loop.py` | Control-loop monitor record tests |
| `spectrum_systems/modules/working_paper_engine/observe.py` | Working paper OBSERVE stage |

The INTERPRET, DECIDE, and ENFORCE layers were not reviewed.

---

## Summary

**Overall status: WARNING**

The BAE OBSERVE layer demonstrates strong structural discipline: every artifact is
schema-validated before return, two distinct monitor record formats are supported, and
the core `build_monitor_record` and `build_validation_monitor_record` paths fail closed
on malformed input. However, three concrete weaknesses prevent a clean PASS. First,
the control-loop path silently inserts sentinel strings (`"unknown-trace"`,
`"unknown-decision"`) for missing traceability IDs — these are schema-valid and pass
validation without error, meaning an untraceable record is indistinguishable from a
correctly traced one. Second, the schema's `allOf` cross-field constraint is
under-specified and does not fully capture the `status / validation_status /
system_response` invariant. Third, the public `compute_alert_recommendation` API uses
best-case defaults for missing fields, producing `{"level": "none"}` on empty input
rather than failing. The test suite is comprehensive for happy-path and common error
cases; the gaps above are not exercised. The system is safe for current production use
but carries latent traceability and schema-drift risk that should be addressed before
the OBSERVE layer is relied on for audit or compliance decisions.

---

## Findings

---

### P1 — Critical (breaks fail-closed or traceability)

#### P1-A: Sentinel traceability IDs silently inserted and schema-valid

**Location:** `evaluation_monitor.py` lines 931–933

```python
"run_id":            str(decision.get("run_id") or "unknown"),
"trace_id":          str(decision.get("trace_id") or "unknown-trace"),
"source_decision_id": str(decision.get("decision_id") or "unknown-decision"),
```

**Why it matters:**
When `run_id`, `trace_id`, or `decision_id` are absent or falsy in the input decision,
the OBSERVE layer silently substitutes the literal strings `"unknown"`,
`"unknown-trace"`, and `"unknown-decision"`. These strings satisfy the schema's
`minLength: 1` constraint and pass schema validation without error. The produced record
appears fully formed but is not traceable to any real execution. A downstream auditor
cannot distinguish a correctly traced record from a sentinel-filled one. This violates
the core traceability invariant.

**Minimal fix:**
Add an explicit guard before constructing the record dict:

```python
missing = [f for f, v in [
    ("run_id", decision.get("run_id")),
    ("trace_id", decision.get("trace_id")),
    ("decision_id", decision.get("decision_id")),
] if not v]
if missing:
    raise EvaluationMonitorError(
        f"artifact_validation_decision missing required traceability fields: {missing}"
    )
```

The indeterminate/malformed guard at line 893 (`if malformed or ...`) handles missing
`validation_results`, but does not catch missing ID fields. The fix above runs before
the record is assembled.

---

### P2 — High (weakens reliability or auditability)

#### P2-A: `compute_alert_recommendation` uses best-case defaults for public API

**Location:** `evaluation_monitor.py` lines 402–405

```python
overall_status = record.get("overall_status", "pass")   # default: PASS
pass_rate      = record.get("pass_rate", 1.0)            # default: 100%
drift_rate     = sli.get("drift_rate", 0.0)              # default: 0%
```

**Why it matters:**
All three defaults represent the best-possible signal value. An external caller passing
an empty or partial record gets `{"level": "none", "reasons": []}` — no alert — rather
than an error. Internally this is protected: `build_monitor_record` constructs the
partial record from validated data before calling this function, so the in-module path
is safe. But `compute_alert_recommendation` is a public exported function
(`__all__`-accessible), and its contract silently passes for any caller that omits
required fields. If an integration test or downstream module calls this function
directly on a partial record, it will silently undercount alerts.

**Minimal fix:**
Add a required-field guard at function entry:

```python
required = {"overall_status", "pass_rate", "sli_snapshot"}
missing = required - set(record)
if missing:
    raise EvaluationMonitorError(
        f"compute_alert_recommendation: missing required fields {missing}"
    )
```

#### P2-B: Schema `allOf` constraint is under-specified

**Location:** `evaluation_monitor_record.schema.json` lines 135–153

The `allOf` rule currently reads:

```json
"if":   { "properties": { "validation_status": {"const": "invalid"} } },
"then": { "not": { "properties": { "status": {"const": "healthy"},
                                   "system_response": {"const": "allow"} } } }
```

**Why it matters:**
This only prevents the `invalid + healthy + allow` triple. It does not enforce the
positive assertion that `status=healthy` requires `validation_status=valid` and
`system_response=allow`. The following combinations are schema-valid but internally
inconsistent:
- `status=healthy` + `validation_status=invalid` + `system_response=block`
- `status=healthy` + `validation_status=valid` + `system_response=block`

The implementation code at lines 898–913 produces only correct combinations, so the
current output is correct. However, if the implementation changes or a record is
constructed outside this module, the schema will not catch inconsistencies. Schema drift
is now a silent risk.

**Minimal fix:**
Add a second `allOf` entry asserting the positive invariant:

```json
{
  "if":   { "properties": { "status": {"const": "healthy"} }, "required": ["status"] },
  "then": {
    "properties": {
      "validation_status": {"const": "valid"},
      "system_response":   {"const": "allow"}
    },
    "required": ["validation_status", "system_response"]
  }
}
```

#### P2-C: Multi-record summary assigns first record's `trace_id` to the window

**Location:** `evaluation_monitor.py` line 990

```python
first_trace_id = str(records[0]["trace_id"])
```

**Why it matters:**
When `summarize_validation_monitor_records` aggregates N records from N distinct
traces, the resulting summary's `trace_id` field is the trace ID of the first record in
the list. Downstream consumers that rely on `summary.trace_id` to identify which
execution the summary covers will receive an incomplete answer — one of N trace IDs,
not a representation of the full window. This is a partial traceability break in any
multi-trace window.

**Minimal fix:**
Document the limitation explicitly in the function docstring and add a comment at
line 990. For a more complete fix, expose a `source_trace_ids` array in the summary
(mirroring `source_run_ids` in the legacy summary) so the window's full provenance is
accessible without relying on a single `trace_id`.

---

### P3 — Medium (improvement / hardening)

#### P3-A: `assess_burn_rate([])` returns `"normal"` when called standalone

**Location:** `evaluation_monitor.py` lines 545–546

```python
if not records:
    return {"status": "normal", "reasons": ["No records to assess."]}
```

**Why it matters:**
`summarize_monitor_records` raises on empty input before reaching `assess_burn_rate`,
so the in-module path is protected. But `assess_burn_rate` is a public exported
function. A standalone caller passing an empty list receives `status=normal` — a clean
bill of health — rather than an error. This is fail-open for the public API surface.

**Suggested fix:**
Raise `EvaluationMonitorError` on empty input, consistent with the fail-closed
principle stated in the module docstring:

```python
if not records:
    raise EvaluationMonitorError("assess_burn_rate requires at least one record.")
```

#### P3-B: `avg_repro` uses 0.0 as a silent defensive fallback

**Location:** `evaluation_monitor.py` line 283

```python
avg_repro = summary_block.get("average_reproducibility_score", 0.0)
```

**Why it matters:**
`_validate_input` runs before this line, and `regression_run_result.schema.json`
requires `average_reproducibility_score`. So in the current system, schema validation
catches any missing field before this code is reached. The risk is latent: if the
schema is ever relaxed or validation bypassed (e.g., in a testing shortcut), the
fallback of 0.0 is a meaningful SLI value (worst-case reproducibility) rather than a
neutral sentinel. It would silently produce misleading SLI data without raising.

**Suggested fix:**
Remove the defensive default and let the KeyError surface:

```python
avg_repro = summary_block["average_reproducibility_score"]
```

This aligns with the fail-closed design principle and makes any schema relaxation
immediately visible.

#### P3-C: `run_evaluation_monitor` batch API cannot enforce `require_replay` policy

**Location:** `evaluation_monitor.py` lines 806–857

```python
record = build_monitor_record(run_result)   # require_replay not passed
```

**Why it matters:**
`build_monitor_record` accepts a `require_replay` keyword argument that enforces
replay analysis must be provided. The batch entry point `run_evaluation_monitor` does
not expose this parameter, so replay enforcement must be re-implemented at every call
site that uses the batch API. There is no mechanism for a policy operator to configure
replay enforcement at the batch level without bypassing the batch API entirely.

**Suggested fix:**
Add `require_replay: bool = False` to `run_evaluation_monitor`'s signature and
thread it through to `build_monitor_record(run_result, require_replay=require_replay)`.

#### P3-D: Legacy monitor records carry no `trace_id` field

**Why it matters:**
Legacy `evaluation_monitor_record` artifacts carry `source_run_id` and
`source_suite_id` but no `trace_id`. Individual execution-trace traceability is only
accessible by inspecting the `results` array of the source `regression_run_result`
artifact. A monitor record cannot be directly linked to a specific trace without
retrieving the original input artifact. This is a traceability gap at the record level
for audit purposes.

**Suggested fix:**
This is an architectural gap in the legacy format. A non-breaking option: include an
optional `source_trace_ids` array field in the legacy schema populated from
`results[*].trace_id` during `build_monitor_record`. The field can remain optional for
backward compatibility.

---

## Top 5 Immediate Fixes

**Ranked by impact on safety and auditability:**

1. **(P1-A) Guard against sentinel traceability IDs in `build_validation_monitor_record`.**
   Add an explicit check that raises `EvaluationMonitorError` when `run_id`, `trace_id`,
   or `decision_id` are absent from the input decision, before any record construction.

2. **(P2-B) Add positive `status=healthy` constraint to the schema `allOf`.**
   Extend the schema to assert that `healthy` status implies `valid` validation_status
   and `allow` system_response. This closes the contract gap without changing code logic.

3. **(P2-A) Add required-field guard to `compute_alert_recommendation`.**
   Raise `EvaluationMonitorError` if `overall_status`, `pass_rate`, or `sli_snapshot`
   are absent. This closes the public API's fail-open surface.

4. **(P2-C) Document and surface multi-trace window trace_id limitation.**
   At minimum add a docstring warning. Ideally expose `source_trace_ids` in the summary
   for multi-record windows.

5. **(P3-A) Make `assess_burn_rate([])` fail closed.**
   Replace the `"normal"` default on empty input with a raised error, consistent with
   the module's stated fail-closed principle.

---

## Pass/Fail Against Invariants

| Invariant | Status | Notes |
|---|---|---|
| **Fail-Closed** | PARTIAL | Core record-build paths fail closed on invalid input. Public APIs `compute_alert_recommendation` and `assess_burn_rate` have fail-open defaults. |
| **Schema Compliance** | PARTIAL | All produced artifacts are validated before return. Schema `allOf` constraint is under-specified and does not enforce the full status/response invariant. Sentinel IDs ("unknown-trace") are schema-valid, masking traceability failures. |
| **Traceability** | PARTIAL | Control-loop records allow sentinel IDs to pass. Multi-trace summary trace_id represents only the first record. Legacy records carry no trace_id at the record level. |
| **Determinism** | PASS | All SLI computations are deterministic from input data. `_compute_replay_consistency_sli`, `classify_trend`, `_safe_divide`, and `_bit` are deterministic. Record and summary IDs use UUID4 (expected non-determinism). |
| **Single Source of Truth** | PASS | SLI values are computed once and stored in the record. `avg_repro` appears in both the record root and `sli_snapshot`, but both are populated from the same variable at construction time. |

---

## Gaps Not Covered

The following are explicitly out of scope for this review:

- INTERPRET layer (`evaluation_budget_governor.py`, policy interpretation logic)
- DECIDE layer (budget decision construction)
- ENFORCE layer (enforcement execution, blocking mechanisms)
- `run_bundle_validator.py` (input-side validation engine, upstream of OBSERVE)
- `evaluation_auto_generation.py` (failure case generation, downstream of OBSERVE)
- `working_paper_engine/observe.py` — reviewed for completeness as it carries the
  "observe" label, but this module serves the Working Paper Engine pipeline (document
  extraction), not the BAE monitor_record control loop. It is architecturally separate
  and its findings (no schema validation on output, no fail-closed on empty input) are
  out of scope for this BAE-focused review.
- Future schema versions or proposed format changes
- Performance or operational characteristics of the monitor runtime
