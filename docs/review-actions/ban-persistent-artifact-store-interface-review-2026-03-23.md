# BAN Persistent Artifact Store Interface — Surgical Implementation Review

**Date:** 2026-03-23

## Scope Reviewed
- `spectrum_systems/modules/**/artifact_store*.py`
- `spectrum_systems/modules/**/store*.py`
- `spectrum_systems/modules/runtime/`
- `contracts/schemas/*artifact*.json` where store identity/linkage appears
- Tests relevant to artifact persistence, IDs, overwrite behavior, and replay/storage interactions

## Evidence Commands
- `rg --files spectrum_systems/modules | rg '(artifact_store.*\\.py|/store.*\\.py)'`
- `pytest -q tests/test_trace_store.py tests/test_replay_engine.py`

## Decision
**FAIL**

## Critical Findings (max 5)

### 1) Store is mutable (overwrite + delete), not immutable
- **What is wrong**
  - `persist_trace()` writes to a fixed `<trace_id>.json` target and uses `os.replace(...)`, which replaces existing files.
  - `delete_trace()` allows permanent deletion.
  - Tests explicitly assert overwrite behavior as expected.
- **Why dangerous**
  - Existing persisted artifacts can be silently replaced or removed, breaking append-only audit guarantees.
- **Location**
  - `spectrum_systems/modules/runtime/trace_store.py` (`persist_trace`, `_atomic_write`, `delete_trace`)
  - `tests/test_trace_store.py` (idempotent overwrite and delete expectations)
- **Realistic failure scenario**
  - A rerun with the same `trace_id` replaces the original file; incident review later cannot recover the original persisted record.

### 2) Storage identity linkage is under-constrained
- **What is wrong**
  - `load_trace(trace_id)` validates schema but does not enforce `envelope.trace.trace_id == trace_id`.
  - Schema does not bind `storage_path` and inner `trace_id` to canonical path semantics.
- **Why dangerous**
  - A schema-valid but mislinked record can be loaded under the wrong requested identity.
- **Location**
  - `spectrum_systems/modules/runtime/trace_store.py` (`load_trace`)
  - `contracts/schemas/persisted_trace.schema.json`
- **Realistic failure scenario**
  - `trace-A.json` contains `trace.trace_id = trace-B`; callers load `trace-A` and trust wrong identity payload.

### 3) Replay artifact identity falls back to permissive placeholders
- **What is wrong**
  - Replay result construction falls back across multiple IDs and uses placeholder defaults (`unknown-*`) for references.
- **Why dangerous**
  - Schema-valid artifacts can carry semantically weak linkage/provenance and become ambiguous in audits.
- **Location**
  - `spectrum_systems/modules/runtime/replay_engine.py` (`_build_replay_result`)
  - `contracts/schemas/replay_result.schema.json` (minLength constraints without strong reference patterns)
- **Realistic failure scenario**
  - Partial upstream context produces replay records with placeholder references that cannot be deterministically joined to source decisions.

### 4) Runtime ↔ replay storage parity is weak/non-unified
- **What is wrong**
  - Runtime traces use durable file persistence via `trace_store`.
  - Replay outputs are returned as dict artifacts in-memory in reviewed path; no equivalent immutable persistence guard is enforced here.
- **Why dangerous**
  - Runtime and replay records are not held to the same storage immutability/identity guarantees.
- **Location**
  - `spectrum_systems/modules/runtime/trace_store.py`
  - `spectrum_systems/modules/runtime/replay_engine.py`
- **Realistic failure scenario**
  - Durable runtime trace exists, but replay evidence is regenerated or handled transiently without equivalent persistence integrity controls.

## Required Fixes (minimal, surgical)
1. **Block overwrite in `persist_trace`**
   - If destination already exists, raise hard failure (fail closed).
2. **Remove hard delete semantics for governed persisted traces**
   - Either disallow delete or convert to explicit tombstone/archive semantics.
3. **Enforce cross-field identity checks**
   - On load: assert requested `trace_id` equals `envelope.trace.trace_id` and `storage_path` matches canonical path.
4. **Fail on missing replay linkage IDs**
   - Remove `unknown-*` defaults for replay references; raise instead.
5. **Tighten replay schema linkage fields**
   - Apply stronger patterns/constraints for decision/enforcement references beyond `minLength`.

## Optional Improvements
- Add immutable lineage fields to persisted trace envelopes (e.g., content hash, supersedes pointer).
- Strengthen persisted trace schema constraints for `trace.artifacts[*]` identity fields.
- Add tests that assert overwrite attempts fail and ID/path mismatches are rejected.

## Trust Assessment
**NO**

## Failure Mode Summary
The worst realistic failure is silent replacement or deletion of persisted runtime trace records combined with replay artifacts carrying weak placeholder linkage. That combination undermines auditability and makes replay-based trust conclusions non-defensible.
