# Review → Eval Hardening Report

Date: 2026-04-03
Batch: BATCH-R

## Scope assessed
- `spectrum_systems/modules/runtime/review_signal_extractor.py`
- `spectrum_systems/modules/runtime/review_eval_bridge.py`
- `spectrum_systems/modules/runtime/evaluation_control.py`
- `spectrum_systems/modules/runtime/evaluation_auto_generation.py`

## Findings

1. **Untyped review taxonomy drift risk** (Severity: High)
   - Prior state accepted arbitrary `review_type` strings, enabling drift between trigger policy and control ingest.
   - Fix: enforce normalized review types (`surgical`, `failure`, `batch_architecture`, `hard_gate`, `strategic`) and reject unknown values fail-closed.

2. **Missing typed request in review trigger artifacts** (Severity: High)
   - Prior trigger artifact did not carry structured `review_request` data required for deterministic replay/audit.
   - Fix: add governed `review_request` contract and embed in `prompt_queue_review_trigger` when trigger is active.

3. **Required-review type enforcement gap in control** (Severity: Critical)
   - Prior control could require “a review” but not specific review classes.
   - Fix: add `required_review_types` enforcement and force `deny_missing_required_signal` when required types are missing.

4. **Limited review observability outputs** (Severity: Medium)
   - Prior bridge had no strict artifacts for review fail-rate hotspots or review-driven eval generation summaries.
   - Fix: add deterministic summary/hotspot/generation report artifacts with strict schemas.

5. **Review-failure recurrence not surfaced as priority** (Severity: Medium)
   - Prior review-failure eval generation deduped, but recurrence intensity did not deterministically mark priority.
   - Fix: recurrence-aware provenance and high-priority threshold tagging.

## Integrity confirmations
- Review PASS cannot override stronger BLOCK/DENY decisions.
- Review FAIL always yields deny/block when consumed.
- Malformed review signals continue to fail closed via schema validation.
- Canonical ordering is preserved via stable sort and canonical JSON hashing in ID/report generation.

## Proposed follow-ups
- Add optional hard bind from `review_request.review_id` to emitted `review_control_signal.review_id` in runtime ingestion seams.
- Add periodic batch job for fleet-level review hotspot rollups once scheduler seam is finalized.
