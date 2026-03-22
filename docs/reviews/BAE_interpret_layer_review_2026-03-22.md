# BAE Interpret Layer Review — 2026-03-22

## Scope
This review is strictly limited to the INTERPRET layer behavior exercised by:
- `spectrum_systems/modules/runtime/evaluation_monitor.py`
- `contracts/schemas/evaluation_monitor_summary.schema.json`
- `contracts/schemas/evaluation_monitor_record.schema.json`
- `tests/test_evaluation_monitor.py`
- `tests/test_evaluation_control_loop.py`

No implementation, schema, or test modifications were performed.

## Summary
- Overall status: **FAIL**

The INTERPRET layer cannot currently be trusted as fully semantically correct and fail-closed for control-loop summaries. The implementation has concrete fail-open and semantic-consistency gaps where malformed/partial decision payloads can still produce `healthy` monitor records, and aggregated summaries lose source-level traceability while also being order-dependent for `trace_id`. Schema constraints permit logically inconsistent enum combinations, and the test surface does not cover these specific failure modes. Because these issues can produce misleading confidence and weaken auditability, the result is not PASS.

## Findings

### P1 (Critical — fail-open, misleading, or audit-breaking)

- **Finding**: `build_validation_monitor_record` can emit `status="healthy"`, `validation_status="valid"`, `system_response="allow"` even when required validation flags are missing/false.
- **Why it matters**: This is a fail-open semantic mismatch. A partial or inconsistent decision can be represented as healthy despite SLI bits indicating failures (`manifest_valid=0`, etc.) and `bundle_validation_success_rate=0.0`. This creates false confidence at record level and can contaminate downstream interpretation.
- **Minimal fix**: Gate the healthy branch on both `(status==valid && system_response==allow)` **and** all required `validation_results` booleans being explicitly true; otherwise force `failed` or `indeterminate` with block/rebuild response.
- **Affected files**:
  - `spectrum_systems/modules/runtime/evaluation_monitor.py`
  - `contracts/schemas/evaluation_monitor_record.schema.json`
  - `tests/test_evaluation_control_loop.py`

- **Finding**: Summary provenance is audit-breaking for aggregated control-loop records.
- **Why it matters**: `summarize_validation_monitor_records` collapses many records into a summary that keeps only the first record’s `trace_id` and no list of source `record_id` / `run_id` / `decision_id`. For mixed-record windows, traceability to all source records is lost and can be misleading.
- **Minimal fix**: Add explicit source provenance arrays in summary contract (e.g., source record IDs and trace/run IDs) and enforce deterministic ordering.
- **Affected files**:
  - `spectrum_systems/modules/runtime/evaluation_monitor.py`
  - `contracts/schemas/evaluation_monitor_summary.schema.json`
  - `tests/test_evaluation_control_loop.py`

### P2 (High — weakens reliability or semantic integrity)

- **Finding**: Control-loop record schema allows logically inconsistent combinations that are enum-valid.
- **Why it matters**: Current schema only forbids one specific invalid pair (`validation_status=invalid` with both `status=healthy` and `system_response=allow`). It still permits inconsistent states such as `status=healthy` + `validation_status=invalid` + `system_response=block`, or `status=failed` + `validation_status=valid`.
- **Minimal fix**: Add explicit cross-field constraints (`if/then` matrix) to fully encode allowed combinations.
- **Affected files**:
  - `contracts/schemas/evaluation_monitor_record.schema.json`
  - `tests/test_evaluation_control_loop.py`

- **Finding**: Control-loop summary output is not deterministic for equivalent input sets and is partially order-dependent.
- **Why it matters**: `summary_id` and `generated_at` are non-deterministic per call, and `trace_id` is derived from `records[0]`. Equivalent record sets in different orders can produce different summary `trace_id`, weakening reproducibility and audit comparisons.
- **Minimal fix**: Define deterministic provenance semantics (e.g., sorted source IDs or explicit multi-source field) and separate non-deterministic envelope metadata from semantic summary payload.
- **Affected files**:
  - `spectrum_systems/modules/runtime/evaluation_monitor.py`
  - `contracts/schemas/evaluation_monitor_summary.schema.json`
  - `tests/test_evaluation_control_loop.py`

- **Finding**: Public helper `compute_alert_recommendation` defaults missing inputs to best-case values.
- **Why it matters**: At API boundary, absent `overall_status`, `pass_rate`, or `sli_snapshot` can quietly yield `level="none"` instead of raising. This is fail-open behavior if called outside tightly controlled internal paths.
- **Minimal fix**: Enforce required fields at function boundary (raise on missing/invalid policy inputs) or mark function internal-only.
- **Affected files**:
  - `spectrum_systems/modules/runtime/evaluation_monitor.py`
  - `tests/test_evaluation_monitor.py`

### P3 (Medium — hardening or coverage gap)

- **Finding**: No low-data confidence guard for control-loop summary classification.
- **Why it matters**: A single healthy record yields `overall_status="healthy"` with no minimum sample-size or confidence caveat. This can overstate reliability under sparse data.
- **Suggested fix**: Add minimum-window policy (or explicit low-sample reason/status downgrade) and tests for 1-record and 2-record mixed scenarios.
- **Affected files**:
  - `spectrum_systems/modules/runtime/evaluation_monitor.py`
  - `tests/test_evaluation_control_loop.py`

- **Finding**: Missing negative tests for semantic and determinism edge cases.
- **Why it matters**: Current tests validate nominal mappings and status thresholds, but do not lock down contradictions between status/SLI flags, order dependence of summary provenance, or helper fail-open defaults.
- **Suggested fix**: Add targeted tests for contradictory payloads, reordered equivalent record sets, and strict boundary validation behavior.
- **Affected files**:
  - `tests/test_evaluation_monitor.py`
  - `tests/test_evaluation_control_loop.py`

## Top 5 Immediate Fixes
1. Fail closed in `build_validation_monitor_record`: never emit `healthy/valid/allow` unless all required validation flags are explicitly true.
2. Add complete schema-level combination constraints for `status`, `validation_status`, and `system_response`.
3. Add full source provenance to control-loop summary (record/run/trace/decision identifiers), not just a single `trace_id`.
4. Remove order-dependence in summary provenance fields (deterministic ordering + explicit multi-source representation).
5. Harden API boundary for `compute_alert_recommendation` (reject missing required fields) and add negative tests.

## Pass/Fail Against Invariants
- **Fail-Closed**: **FAIL** (critical fail-open path for partial decision payloads reaching healthy status)
- **Schema Compliance**: **PARTIAL** (schema validates structure but permits semantically invalid combinations)
- **Semantic Integrity**: **FAIL** (record-level healthy status can contradict failing SLI bits)
- **Determinism**: **PARTIAL** (aggregates deterministic; provenance/id fields are non-deterministic/order-dependent)
- **Traceability**: **FAIL** (summary cannot tie back to all source records)
- **Single Source of Truth**: **PARTIAL** (contracts exist, but do not fully enforce required semantic invariants)

## Recommended Follow-Up Tests
1. `build_validation_monitor_record` rejects or downgrades to non-healthy when any required validation flag is missing/false despite `status=valid` + `system_response=allow`.
2. Schema conformance tests for disallowed cross-field combinations across `status`/`validation_status`/`system_response`.
3. `summarize_validation_monitor_records` equivalence test: same records in different order produce semantically identical provenance.
4. Traceability test: summary contains complete source record linkage for all inputs.
5. Boundary test for `compute_alert_recommendation`: missing required inputs raises explicit error (no best-case defaults).

## Gaps Not Covered
- Downstream budget-governor decision logic outside INTERPRET aggregation internals.
- Run-bundle validator implementation details outside what is directly surfaced in monitor records.
- Any non-target module, schema, or workflow not listed in scope.

**Trustworthiness answer:** **No** — the INTERPRET layer is not yet trustworthy for semantically correct, fail-closed summaries without the fixes above.
