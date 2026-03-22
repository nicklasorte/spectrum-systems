# BAJ Provenance Hardening — Phase 1 Fix Report

## Date
2026-03-22

## Scope
Narrow Phase 1 hardening of the primary provenance spine only:
- authoritative schema selection for the primary runtime path
- shared artifact metadata policy identity hardening
- study-runner provenance trace linkage + fail-closed behavior
- runtime-derived provenance values (no static literals)
- primary-path emission-time validation

Out of scope: repo-wide provenance model consolidation, strategic-knowledge provenance redesign, historical backfill, and contract-layer unification.

## Authoritative schema decision
For this Phase 1 runtime spine patch, the authoritative provenance schema is:
- `schemas/provenance-schema.json`

Rationale:
- It already matched the study-runner provenance shape (record-level provenance attached to produced artifacts).
- It enforces the repo-native versioned policy-id pattern used by provenance records.
- It was the least disruptive path to make primary emitters fail-closed without broad contract migration.

This patch makes the authoritative primary-path schema explicit by:
- requiring `trace_id` and `span_id` in `schemas/provenance-schema.json`
- validating emitted provenance records against this schema in shared emitter + study-runner path

## Files changed
- `docs/review-actions/PLAN-BAJ-PROVENANCE-HARDENING-PHASE1-2026-03-22.md`
- `PLANS.md`
- `schemas/provenance-schema.json`
- `shared/artifact_models/artifact_metadata.schema.json`
- `shared/adapters/artifact_emitter.py`
- `spectrum_systems/study_runner/artifact_writer.py`
- `spectrum_systems/study_runner/run_study.py`
- `tests/test_provenance_schema.py`
- `tests/test_lifecycle_enforcer.py`
- `tests/test_artifact_packaging_and_study_state.py`

## Finding-to-fix mapping
### Finding 1 — Trace context absent in study-runner provenance
- `write_outputs()` now requires explicit `trace_id` + `span_id`.
- Trace context is validated via `validate_trace_context(trace_id, span_id)` before artifact writes.
- Invalid/missing trace context hard-fails before any output write.
- Provenance now includes `trace_id` and `span_id` and validates against authoritative schema.

### Finding 2 — Shared emitter omits `policy_id`
- `create_artifact_metadata()` now requires `policy_id` (no default/fallback).
- `policy_id` is validated against the repo-native versioned pattern.
- Emitted metadata now includes `policy_id`.
- Metadata is validated against `shared/artifact_models/artifact_metadata.schema.json` before return.

### Finding 4 — Static hardcoded provenance values
- Removed static study-runner provenance literals (`rev0`, `design-notebook`, static policy literal).
- `policy_id`, `generated_by_version`, and `source_revision` are now required runtime inputs to `write_outputs()`.
- `run_study.py` now resolves runtime provenance inputs explicitly:
  - `generated_by_version` from `git rev-parse --short=12 HEAD`
  - `source_revision` from source config file stat-derived revision token
  - `policy_id` from active `config/regression_policy.json`

### Finding 5 (bounded) — schema ambiguity
- Bounded fix only: primary runtime path now explicitly validates against `schemas/provenance-schema.json`.
- Added required trace linkage fields to this schema to align with runtime trace requirements.
- Full three-schema consolidation is deferred.

## Test evidence
- `pytest -q tests/test_provenance_schema.py` (pass)
- `pytest -q tests/test_lifecycle_enforcer.py` (pass)
- `pytest -q tests/test_artifact_packaging_and_study_state.py` (pass)
- `pytest -q tests/test_artifact_envelope.py` (pass)
- `pytest -q tests/test_trace_engine.py` (pass)
- `pytest -q tests/test_policy_registry.py` (pass)
- `pytest -q` (pass)

## Remaining gaps (explicitly deferred)
- Full convergence of:
  - `governance/schemas/provenance.schema.json`
  - `schemas/provenance-schema.json`
  - `contracts/schemas/provenance_record.schema.json`
- Strategic-knowledge provenance still uses a separate model and was not replaced in this narrow Phase 1 patch.
- Contract-layer provenance schema (`contracts/schemas/provenance_record.schema.json`) remains structurally distinct from this runtime path.
