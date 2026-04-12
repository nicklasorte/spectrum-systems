# PLAN — DASHBOARD-UI-FIX-TRUTH-BOUNDARY-02 (2026-04-12)

## Prompt type
BUILD

## Scope
Surgical hardening of dashboard UI truth boundary to remove remaining UI-layer governance decision logic and enforce fail-closed artifact handling.

## Objectives
1. Remove selector-generated prescriptive recommendation fallback and replace with abstention-only fallback.
2. Make recommendation/global provenance factual, field-level where known, and explicitly low-confidence where unknown.
3. Enforce strict manifest validation for publication_state, artifact_count, required_files shape/uniqueness/count coherence.
4. Remove filename token heuristic classification in artifact explorer and replace with explicit mapping.
5. Add tests for abstention fallback, provenance uncertainty signaling, strict manifest validation, and no heuristic classification.

## Execution steps
1. Update dashboard validation rules for `dashboard_publication_manifest.json` with strict enum/count/array uniqueness checks.
2. Update dashboard selectors:
   - abstention-only recommendation fallback (no prescriptive action),
   - factual provenance rows + explicit low confidence on unknown fields,
   - explicit artifact-family mapping table (no `includes()` classifier).
3. Update dashboard types to carry provenance confidence metadata.
4. Add/adjust dashboard contract tests covering required blockers.
5. Run `pytest` and dashboard build (`npm --prefix dashboard run build`) and resolve regressions.

## Constraints honored
- No new feature surfaces.
- No layout/visual changes.
- No weakening of render gates.
- No policy logic reintroduced in UI fallbacks.
