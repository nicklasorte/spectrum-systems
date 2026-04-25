# H01 Pre-MVP Spine Review

**Review ID:** H01-REVIEW  
**Date:** 2026-04-25  
**Scope:** BATCH-H01 — PRE-1 through PRE-5 (Contracts + Artifact Store + PQX Harness + Eval + TLC)  
**Reviewer:** Adversarial Review Agent (ARA-01)  
**Method:** Adversarial red-team analysis of all five implemented components

---

## 1. Executive Summary

PRE-1 through PRE-5 implement the foundational governed runtime spine for the transcript-to-study pipeline. The implementation is artifact-first, fail-closed, and trace-enforced. Red-team analysis identified findings across schema enforcement, execution boundary coverage, and observability.

**Overall gate decision:** CONDITIONAL PASS (after S2 fixes applied)

---

## 2. Scope of Review

| Component | File | Status |
|-----------|------|--------|
| PRE-1: Schemas | `contracts/schemas/transcript_pipeline/*.schema.json` | Reviewed |
| PRE-2: Artifact Store | `spectrum_systems/modules/runtime/artifact_store.py` | Reviewed |
| PRE-3: PQX Harness | `spectrum_systems/modules/orchestration/pqx_step_harness.py` | Reviewed |
| PRE-4: Eval Runner | `spectrum_systems/modules/evaluation/pipeline_eval_runner.py` | Reviewed |
| PRE-5: TLC Router | `spectrum_systems/modules/orchestration/tlc_router.py` | Reviewed |

---

## 3. Findings

### F-001: Replay Consistency Eval — No Canonical Replay Driver (S2)

**Severity:** S2 (Significant gap)  
**Component:** PRE-4 (pipeline_eval_runner.py)  
**Description:** The `replay_consistency` eval requires callers to supply a `replay_fn`. There is no governed canonical replay driver that enforces deterministic re-execution. A caller can pass a non-deterministic `replay_fn` (e.g., wrapping a random function), making the eval vacuous. The eval has no way to detect this.  
**Risk:** Silent consistency bypass — a non-deterministic execution function could pass by accident.  
**Recommendation:** Document that `replay_fn` must produce deterministic output from the same inputs. Add a test verifying the eval catches non-determinism across two runs.

### F-002: PQX Harness — No Output Artifact Type Enforcement (S2)

**Severity:** S2 (Significant gap)  
**Component:** PRE-3 (pqx_step_harness.py)  
**Description:** `run_pqx_step` accepts any artifact type as output from `execution_fn`. There is no enforcement that the output artifact type matches the expected output for the declared `step_name`. A step named `normalize_transcript` could return a `release_artifact` without being blocked.  
**Risk:** Artifact type injection — execution can produce wrong-type outputs that bypass routing.  
**Recommendation:** Add an optional `expected_output_type` parameter to `run_pqx_step`. When provided, enforce it before registering the artifact.

### F-003: Schema — `context_bundle` Not Covered by Transcript Pipeline Schemas (S2)

**Severity:** S2 (Gap in contract coverage)  
**Component:** PRE-1 (contracts/schemas/transcript_pipeline/)  
**Description:** The TLC routing table routes `transcript_artifact → context_bundle`, but `context_bundle` has no schema in `contracts/schemas/transcript_pipeline/`. Any artifact claiming `artifact_type: context_bundle` cannot be schema-validated by the artifact store.  
**Risk:** Unvalidated artifacts enter the pipeline immediately after admission.  
**Recommendation:** Create `contracts/schemas/transcript_pipeline/context_bundle.schema.json`.

### F-004: Artifact Store — No Immutability After Write (S3)

**Severity:** S3 (Architectural invariant gap)  
**Component:** PRE-2 (artifact_store.py)  
**Description:** The in-memory store holds a reference to the original dict. A caller retaining a reference to the artifact dict can mutate it after registration, silently altering the stored artifact without triggering re-validation or hash re-check.  
**Risk:** Post-write artifact mutation bypasses content_hash integrity.  
**Recommendation:** Deep-copy artifacts at write time. Return a copy at read time.

### F-005: TLC Router — No Eval Gate Enforcement Before Routing (S2)

**Severity:** S2 (Control gap)  
**Component:** PRE-5 (tlc_router.py)  
**Description:** `route_artifact()` performs type-based routing but does not verify that required eval gates have passed before emitting the next type. The routing layer has no visibility into eval outcomes.  
**Risk:** A failing artifact can be routed to the next pipeline stage before evals block it.  
**Recommendation:** Document that the TLC caller (not the router) is responsible for enforcing eval gates before calling `route_artifact`. Add a note in the module docstring. This is an architecture documentation gap, not a code bug, since gate enforcement lives in the caller per the TLC authority model.

### F-006: Eval Runner — `schema_conformance` Does Not Verify `content_hash` Matches (S2)

**Severity:** S2 (Integrity gap)  
**Component:** PRE-4 (pipeline_eval_runner.py)  
**Description:** The `schema_conformance` eval validates the artifact's structure against its JSON schema but does not verify that `content_hash` matches the artifact's actual content. An artifact with a stale or incorrect `content_hash` can pass schema conformance.  
**Risk:** Tampered content with valid schema structure passes the eval gate.  
**Recommendation:** Add `content_hash` verification as part of the `schema_conformance` eval.

### F-007: No `__init__.py` Import Guard for Evaluation Module (S4)

**Severity:** S4 (Informational)  
**Component:** PRE-4  
**Description:** `pipeline_eval_runner.py` imports from `artifact_store` using a fully qualified path. If the module path changes, the import silently breaks. No import guard or explicit re-export exists in `evaluation/__init__.py`.  
**Risk:** Low. Module path stability is a configuration concern.  
**Recommendation:** No immediate action required. Note for future refactoring.

---

## 4. Findings Summary

| ID | Severity | Component | Title | Status |
|----|----------|-----------|-------|--------|
| F-001 | S2 | PRE-4 | Replay eval — no canonical replay driver | Fix required |
| F-002 | S2 | PRE-3 | PQX — no output type enforcement | Fix required |
| F-003 | S2 | PRE-1 | `context_bundle` schema missing | Fix required |
| F-004 | S3 | PRE-2 | Artifact store not immutable after write | Fix required |
| F-005 | S2 | PRE-5 | TLC router — no eval gate enforcement | Documentation fix |
| F-006 | S2 | PRE-4 | `schema_conformance` skips hash check | Fix required |
| F-007 | S4 | PRE-4 | No import guard in evaluation __init__ | Informational |

---

## 5. Passed Checks

- All 10 schemas enforce `additionalProperties: false` ✓  
- All schemas require `artifact_id`, `schema_ref`, `content_hash`, `trace`, `provenance` ✓  
- Artifact store rejects artifacts with missing trace or provenance ✓  
- Artifact store rejects duplicate artifact_ids ✓  
- Content hash is deterministic SHA-256 over canonical JSON ✓  
- PQX harness always emits `pqx_execution_record` on success and failure ✓  
- PQX harness is fail-closed (missing output, schema violation, exception all block) ✓  
- Eval runner blocks on missing eval types (fail-closed) ✓  
- TLC routing table has no cycles (verified at module load) ✓  
- All 162 tests pass ✓  
- No silent failures — all error paths carry `reason_codes` ✓  

---

## 6. Gate Decision

S3 finding (F-004) and S2 findings (F-001, F-002, F-003, F-006) require fixes before PRE-1 through PRE-5 are considered green.

F-005 requires a documentation fix only. F-007 is informational — no fix required.

**BLOCK until S2+ findings are addressed by H01_fix_plan.**
