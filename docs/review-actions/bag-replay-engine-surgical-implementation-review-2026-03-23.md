# BAG Replay Engine — Surgical Implementation Review

**Date:** 2026-03-23  
**Decision:** **FAIL**

## Scope Reviewed
- `spectrum_systems/modules/runtime/replay_engine.py`
- `spectrum_systems/modules/runtime/replay_decision_engine.py`
- `contracts/schemas/replay_result.schema.json`
- `contracts/schemas/replay_decision_analysis.schema.json`
- `tests/test_replay_engine.py`
- `tests/test_replay_decision_engine.py`

## Critical Findings

### 1) Canonical schema enforcement is not exclusive; legacy fallback is active
**What is wrong**  
`validate_replay_result()` accepts payloads that fail canonical `replay_result.schema.json` if they pass `_LEGACY_REPLAY_RESULT_SCHEMA`.

**Why it is dangerous**  
Semantically weaker/older replay artifacts can pass validation in governed flows, undermining contract uniqueness and audit comparability.

**Location**  
- `spectrum_systems/modules/runtime/replay_engine.py` (`validate_replay_result`)

**Realistic failure scenario**  
A replay artifact missing canonical linkage/provenance fields still passes via legacy shape; downstream audit assumes BAG-governed guarantees that were never enforced.

---

### 2) `execute_replay()` emits non-canonical `replay_result` artifacts
**What is wrong**  
`execute_replay()` builds a BP-style payload (`source_trace_id`, `replayed_at`, `status`, `steps_executed`, etc.) under `artifact_type = replay_result`, but canonical BAG schema requires fields like `original_run_id`, `replay_run_id`, enforcement references, and canonical provenance.

**Why it is dangerous**  
This creates dual semantics under one artifact type and allows runtime↔replay contract drift.

**Location**  
- `spectrum_systems/modules/runtime/replay_engine.py` (`execute_replay` result construction)
- `contracts/schemas/replay_result.schema.json` (required fields)

**Realistic failure scenario**  
A downstream pipeline expecting canonical replay linkage fields receives BP-shaped output and either fails hard or silently downgrades checks.

---

### 3) Post-validation mutation without revalidation
**What is wrong**  
`execute_replay()` validates `result`, then mutates it by adding `decision_analysis`, and returns without revalidating.

**Why it is dangerous**  
Returned artifacts can violate schema (e.g., `additionalProperties: false`) while being treated as validated.

**Location**  
- `spectrum_systems/modules/runtime/replay_engine.py` (`run_decision_analysis` block)
- `contracts/schemas/replay_result.schema.json` (`additionalProperties: false`)

**Realistic failure scenario**  
A caller persists or forwards this “validated” artifact; strict consumers reject it while permissive consumers accept it, splitting audit outcomes.

---

### 4) Replay is not fully deterministic for identical inputs
**What is wrong**  
`_new_id()` and `_now_iso()` are used in replay output generation, and step records include per-step wall-clock timestamps.

**Why it is dangerous**  
Identical replay inputs do not produce identical full artifacts, weakening reproducibility and audit hash stability.

**Location**  
- `spectrum_systems/modules/runtime/replay_engine.py` (`execute_replay`, `_execute_steps`)

**Realistic failure scenario**  
Two replay runs over the same trace produce different payload hashes, triggering false drift alarms in deterministic audit comparisons.

---

### 5) Fail-closed behavior is weakened in analysis integration
**What is wrong**  
When decision analysis fails, `execute_replay(run_decision_analysis=True)` sets `decision_analysis = None` and still returns the replay artifact.

**Why it is dangerous**  
Partial replay artifacts can be emitted in governed flows despite analysis failure.

**Location**  
- `spectrum_systems/modules/runtime/replay_engine.py` (`except ReplayDecisionError: result["decision_analysis"] = None`)
- `tests/test_replay_decision_engine.py` (expects `decision_analysis is None` when no enforcement span)

**Realistic failure scenario**  
A replay run missing enforcement-decision linkage still returns an artifact that can be misinterpreted as complete.

## Required Fixes (minimal, surgical)
1. Remove legacy fallback acceptance from governed `replay_result` validation path (or isolate legacy validator to legacy-only APIs).
2. Ensure only canonical BAG shape is emitted as `artifact_type = replay_result`.
3. Revalidate artifact after any mutation (including `decision_analysis` attachment), or keep analysis artifact out-of-band.
4. Provide deterministic-mode identity fields (and deterministic timestamp strategy) for replay outputs used in strict reproducibility checks.
5. Fail closed when decision analysis is requested but cannot be produced.

## Optional Improvements
- Add a test that explicitly fails if canonical validation fails but legacy validation passes.
- Add a test that `execute_replay(run_decision_analysis=True)` returns a schema-valid replay artifact.
- Add full-payload deterministic snapshot tests for same-input replay runs.

## Trust Assessment
**NO**

## Failure Mode Summary
Worst realistic failure: a replay artifact is accepted as “valid replay_result” through legacy/fallback and mutation-without-revalidation paths, while missing canonical linkage/provenance guarantees. This can produce contradictory audit outcomes across consumers and materially reduce reproducibility trust.
