# Replay blocked-result legacy path review

## Date
2026-03-23

## Scope Reviewed
- `spectrum_systems/modules/runtime/replay_engine.py`
- `tests/test_replay_engine.py`
- `contracts/schemas/replay_result.schema.json`
- `spectrum_systems/modules/runtime/replay_decision_engine.py` (direct consumer of `execute_replay` output in blocked/internal analysis flow)

## Decision (PASS / FAIL)
**FAIL**

## Executive Summary
The legacy replay path is **not safely isolated**. `execute_replay` still returns and can persist legacy-shaped `replay_result` artifacts validated only against `_LEGACY_REPLAY_RESULT_SCHEMA`, not the governed `contracts/schemas/replay_result.schema.json`. This is true for both blocked and non-blocked outputs. A direct internal consumer (`run_replay_decision_analysis`) treats that legacy artifact as authoritative input for follow-on decision logic, so the seam is active, not quarantined.

The canonical BAG replay path (`run_replay`) is strong and schema-governed, but coexistence with `execute_replay` leaves a non-canonical back door for replay semantics in internal persistence and blocked-result handling.

## Findings (ranked P1/P2/P3)

### P1 — Legacy-shaped replay artifacts are still returnable and persistable from active runtime API
- `execute_replay` constructs a legacy shape (`source_trace_id`, `replayed_at`, `status`, etc.), validates with `validate_replay_result_legacy`, and returns it. This happens for blocked and successful replay outputs.
- If `persist_result=True`, this legacy artifact is written immutably to disk.
- The canonical schema requires BAG-specific fields (`original_run_id`, `replay_path`, provenance linkage, strict enums/patterns) that are absent from the legacy path.

**Evidence:**
- Legacy schema definition + validator: `_LEGACY_REPLAY_RESULT_SCHEMA` and `validate_replay_result_legacy`.  
- `execute_replay` uses legacy validation for blocked and normal results, then persists result when requested.  
- Canonical schema requires different fields/shape and forbids extras.

### P1 — Blocked/internal flow does not enforce documented hard-fail behavior for prerequisites
- `run_replay_decision_analysis` comments say blocked replay prerequisites are raised as hard errors.
- In practice, `execute_replay` does **not** raise `ReplayPrerequisiteError` on missing prerequisites; it returns a blocked legacy artifact.
- `recompute_decision_from_replay` then raises on `status == "blocked"`, which is caught and downgraded to indeterminate analysis output instead of hard-failing.

**Why this matters:** blocked replay can bypass expected hard-fail semantics and still produce a downstream analysis artifact.

### P2 — Legacy validator is isolated from canonical validator, but isolation is one-way and incomplete
- `validate_replay_result` correctly validates only canonical schema and does not fallback to legacy.
- Tests explicitly enforce that no legacy fallback occurs in canonical validator.
- However, the runtime still has a live legacy validation entry point used by `execute_replay`, so semantic isolation is incomplete at API level.

### P2 — Post-validation attachment risk exists on legacy path
- `execute_replay` validates legacy result, then optionally appends `decision_analysis` afterward without re-validation.
- Because legacy schema has `additionalProperties: false`, the mutated payload would no longer pass legacy validation if rechecked.

**Why this matters:** this is a validate-then-mutate pattern that weakens trust assumptions about returned objects being schema-conformant after mutation.

### P3 — Non-deterministic IDs/timestamps remain in legacy replay outputs used for internal trust comparisons
- Legacy replay IDs use `uuid4` and timestamps use current wall clock.
- Replay step timestamps are generated per step.
- Canonical `run_replay` uses stable replay ID derivation (`uuid5`) from deterministic seed material.

**Why this matters:** legacy output is less stable for audit/trust diffing across reruns.

## Is legacy path safely isolated?
**No.**

It is only partially isolated:
- Canonical BAG path (`run_replay`) is schema-governed and explicitly canonical.
- But `execute_replay` remains an active runtime path that emits/persists legacy artifacts and is consumed by replay decision analysis flow.

So this is an active compatibility seam with behavioral influence, not a sealed quarantine.

## What could go wrong realistically?
1. **Authoritative confusion:** callers may treat persisted legacy replay artifacts as equivalent to governed BAG replay results.
2. **Blocked-path drift masking:** prerequisites failures can surface as indeterminate analysis artifacts instead of hard-stop errors, obscuring operational issues.
3. **Schema trust erosion:** consumers relying on “validated replay_result” assumptions can process post-validation-mutated payloads.
4. **Audit instability:** non-deterministic IDs/timestamps in legacy outputs complicate reproducibility and trust comparisons.

## Minimal remediation if needed
1. **Gate persistence:** disallow `persist_result=True` for legacy-shaped `execute_replay` outputs, or persist under a distinct artifact type/file namespace that cannot be confused with canonical `replay_result`.
2. **Enforce blocked hard-fail contract:** either (a) make `execute_replay` raise `ReplayPrerequisiteError` for blocked prerequisites in analysis contexts, or (b) update `run_replay_decision_analysis` to explicitly reject blocked replay outputs before indeterminate downgrade.
3. **Remove validate-then-mutate on legacy payload:** if `decision_analysis` is attached, revalidate against an explicit schema that includes that field (or wrap in envelope with separate validated sub-artifacts).
4. **Constrain trust use:** require trust/audit comparison logic to use only canonical `run_replay` output.

## Final trust assessment
The canonical BAG replay path is robust, but the remaining legacy `execute_replay` path is still semantically active and can produce persisted/consumed replay artifacts outside canonical guarantees. For the stated goal (ensuring no back door for non-canonical replay semantics), current state is **unsafe**.
