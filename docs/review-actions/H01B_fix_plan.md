# H01B Fix Plan
**Source Review:** RVA-H01B-SPINE-001  
**Batch:** BATCH-H01B  
**Date:** 2026-04-25  
**Status:** APPLIED

---

## Fix Actions

### FIX-001 — Severity Integrity (F-001)

**Finding:** S4 severity accepted as non-blocking.  
**Target:** `contracts/schemas/transcript_pipeline/review_artifact.schema.json`  
**Action:** Add `if/then` constraint to `review_finding` definition. If `severity == "S4"`, then `blocking` must be `true` and is required.  
**Also:** Update severity description to document S4=halt, S0=informational.  
**Status:** APPLIED

---

### FIX-002 — Gate-Evidence-Enforced Routing (F-002)

**Finding:** Routing possible without gate evidence.  
**Target:** `spectrum_systems/modules/orchestration/tlc_router.py`  
**Action:** Add `route_with_gate_evidence(artifact, gate_evidence, conditional_route_allowed=False)`. Verifies `eval_summary_id` and `gate_status` in the gate evidence object before delegating to `route_artifact`. `failed_gate` and `missing_gate` are rejected_for_route. `conditional_gate` is rejected unless `conditional_route_allowed=True`. TLC does not own control authority — it validates gate evidence produced by an upstream evaluator.  
**Status:** APPLIED

---

### FIX-003 — Canonical Hash Policy (F-003)

**Finding:** `compute_content_hash` included `trace` and `created_at`, making hash metadata-sensitive.  
**Target:** `spectrum_systems/modules/runtime/hash_utils.py` (new), `spectrum_systems/modules/runtime/artifact_store.py` (updated)  
**Action:** Create `hash_utils.py` with canonical exclusion policy (excludes `content_hash`, `trace`, `created_at`). Update `artifact_store.py` to import from `hash_utils` instead of defining the function inline.  
**Status:** APPLIED

---

### FIX-004 — Issue Source Grounding (F-004)

**Finding:** `source_segment_ids` optional in `issue_record`.  
**Target:** `contracts/schemas/transcript_pipeline/issue_registry_artifact.schema.json`  
**Action:** Add `source_segment_ids` to `required` array of `issue_record`. Set `minItems: 1`.  
**Status:** APPLIED

---

### FIX-005 — Decision Traceability (F-005)

**Finding:** Decision records lacked traceability requirement.  
**Target:** `contracts/schemas/transcript_pipeline/meeting_minutes_artifact.schema.json`  
**Action:** Add `source_reference` property to `decision_record`. Add `anyOf: [required: ["source_reference"], required: ["rationale"]]` constraint. Also update `tests/transcript_pipeline/conftest.py` to include `rationale` in the test fixture decision.  
**Status:** APPLIED

---

## Verification

All fixes verified via:
- `tests/transcript_pipeline/test_control_routing_enforcement.py` — 15 gate evidence routing scenarios
- `tests/transcript_pipeline/test_h01b_hardening.py` — 22 severity/hash/grounding scenarios
- `tests/transcript_pipeline/test_artifact_store_h02.py` — existing store tests (no regressions)
- `tests/transcript_pipeline/test_tlc_router_h05.py` — existing router tests (no regressions)
- `tests/transcript_pipeline/test_schemas_h01.py` — existing schema tests (no regressions)
