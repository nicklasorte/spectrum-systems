# H01 Fix Plan

**Fix Plan ID:** H01-FIX-PLAN  
**Date:** 2026-04-25  
**Source Review:** H01-REVIEW / `docs/reviews/H01_pre_mvp_spine_review.md`  
**Scope:** All S2+ findings from the H01 red-team review

---

## Fix Mapping

| Finding | Severity | Fix Action | File |
|---------|----------|-----------|------|
| F-001 | S2 | Add content_hash verification step inside replay_consistency eval | `pipeline_eval_runner.py` |
| F-002 | S2 | Add `expected_output_type` enforcement to `run_pqx_step` | `pqx_step_harness.py` |
| F-003 | S2 | Create `context_bundle.schema.json` | `contracts/schemas/transcript_pipeline/` |
| F-004 | S3 | Deep-copy artifacts at register and retrieve time | `artifact_store.py` |
| F-005 | S2 | Add docstring note to `route_artifact` about eval gate responsibility | `tlc_router.py` |
| F-006 | S2 | Add content_hash verification to `schema_conformance` eval | `pipeline_eval_runner.py` |

---

## Fix Detail

### FIX-001 (F-001 + F-006): Add content_hash verification to evals

**Target:** `spectrum_systems/modules/evaluation/pipeline_eval_runner.py`

`schema_conformance` will verify `content_hash` matches computed hash.
`replay_consistency` will document the determinism requirement in code.

### FIX-002 (F-002): Add expected_output_type enforcement to PQX harness

**Target:** `spectrum_systems/modules/orchestration/pqx_step_harness.py`

Add optional `expected_output_type` parameter. When provided, enforce match before artifact store registration.

### FIX-003 (F-003): Create context_bundle schema

**Target:** `contracts/schemas/transcript_pipeline/context_bundle.schema.json`

### FIX-004 (F-004): Deep-copy artifacts in artifact store

**Target:** `spectrum_systems/modules/runtime/artifact_store.py`

Use `copy.deepcopy()` at register_artifact and retrieve_artifact time.

### FIX-005 (F-005): Document eval gate caller responsibility in TLC router

**Target:** `spectrum_systems/modules/orchestration/tlc_router.py`

Add explicit docstring note.

---

## Regression Test Requirements

- `test_artifact_store_h02.py`: add `TestImmutability` class
- `test_pqx_step_harness_h03.py`: add `TestOutputTypeEnforcement` class
- `test_pipeline_eval_runner_h04.py`: add `TestSchemaConformanceHashCheck` class
- `test_schemas_h01.py`: add `context_bundle` to `EXPECTED_SCHEMAS`
- `test_chaos_h07.py`: add post-write mutation chaos test

---

## Acceptance Criteria

All S2/S3 fixes implemented. All 162 existing tests still pass. New regression tests added for each fix. Full suite green.
