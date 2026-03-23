# BAH Drift Detection Engine — Surgical Implementation Review

- **Date:** 2026-03-23
- **Scope reviewed:**
  - `spectrum_systems/modules/runtime/drift_detection_engine.py`
  - `contracts/schemas/drift_result.schema.json`
  - `contracts/schemas/replay_result.schema.json`
  - `tests/test_drift_detection_engine.py`
  - `spectrum_systems/modules/runtime/replay_engine.py` (drift linkage)

## Decision

**FAIL**

The current implementation is deterministic in normal paths, but it is not fully fail-closed or provenance-safe for malformed/partial inputs.

## Critical Findings

### 1) Early-return classification bypasses canonical replay schema validation
- **What is wrong:** `detect_drift()` emits `missing_original` / `missing_replay` before full `replay_result` schema validation.
- **Why dangerous:** malformed artifacts can still produce drift artifacts instead of hard-failing.
- **Location:** `detect_drift()` missing-key branches before `_validate_or_raise(replay_input, "replay_result", ...)`.
- **Realistic failure scenario:** replay payload missing linkage/provenance plus missing comparison field yields a classified drift artifact that looks valid downstream.

### 2) Drift schema permits semantically weak linkage/provenance IDs
- **What is wrong:** `drift_result.schema.json` only requires non-empty strings for `source_run_id`, `replay_run_id`, and provenance IDs.
- **Why dangerous:** placeholder identifiers like `unknown-*` can pass schema validation.
- **Location:** run-id and provenance fields use `minLength` constraints without anti-placeholder patterns.
- **Realistic failure scenario:** audit and lineage systems ingest artifacts with unusable IDs that still appear contract-valid.

### 3) Drift schema does not enforce consistency invariants
- **What is wrong:** schema allows contradictory tuples (e.g., `drift_type="none"` with `drift_detected=true`).
- **Why dangerous:** semantically contradictory artifacts can pass validation and mislead governance automation.
- **Location:** missing `if/then` constraints tying `drift_type`, `drift_detected`, and `drift_severity`.
- **Realistic failure scenario:** upstream bug emits impossible combinations; validators pass them.

### 4) Direct API path can evaluate non-canonical replay artifacts
- **What is wrong:** canonical replay integration path is strong, but standalone `detect_drift()` can still classify from malformed dicts because of finding #1.
- **Why dangerous:** external callers may bypass replay contract gates yet still produce “official-looking” drift results.
- **Location:** `replay_engine` canonical path validates replay artifact after drift attach; standalone detector remains permissive on early branches.
- **Realistic failure scenario:** batch tooling calls `detect_drift()` on legacy payloads and emits governed-looking drift outputs.

## Required Fixes (minimal, surgical)

1. In `detect_drift()`, validate `replay_result` schema before missing-field drift classification.
2. Tighten `drift_result.schema.json` ID/linkage fields with anti-placeholder patterns (parity with replay schema).
3. Add schema invariants (`if/then`) that bind `drift_type`, `drift_detected`, and `drift_severity` combinations.

## Optional Improvements

- Add regression test: malformed replay payload with missing linkage + missing comparison key must raise `DriftDetectionError` (not emit drift artifact).
- Add negative schema tests for placeholder IDs in drift artifacts.

## Trust Assessment

**NO**

## Failure Mode Summary

Worst realistic failure: malformed or legacy replay payloads produce schema-valid drift artifacts with weak/placeholder provenance, causing audit consumers to trust non-reproducible lineage and degrading confidence in drift governance.
