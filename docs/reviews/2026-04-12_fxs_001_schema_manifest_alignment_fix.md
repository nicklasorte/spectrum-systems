# FXS-001 Schema/Manifest Alignment Fix — 2026-04-12

## 1. Root cause
NXS-001 published nine NX schemas under `contracts/schemas/nx_*.schema.json`, while `contracts/standards-manifest.json` declared the corresponding artifact types without the `nx_` prefix (e.g., `artifact_intelligence_index`). The bootstrap test derives canonical schema paths directly from manifest `artifact_type`, so the declared schema files were missing.

## 2. Files changed
- `docs/review-actions/PLAN-FXS-001-2026-04-12.md`
- `contracts/schemas/` renamed canonical files:
  - `nx_artifact_intelligence_index.schema.json` -> `artifact_intelligence_index.schema.json`
  - `nx_artifact_intelligence_report.schema.json` -> `artifact_intelligence_report.schema.json`
  - `nx_fused_signal_record.schema.json` -> `fused_signal_record.schema.json`
  - `nx_multi_run_aggregate.schema.json` -> `multi_run_aggregate.schema.json`
  - `nx_pattern_mining_recommendation.schema.json` -> `pattern_mining_recommendation.schema.json`
  - `nx_decision_explainability_artifact.schema.json` -> `decision_explainability_artifact.schema.json`
  - `nx_system_trust_score_artifact.schema.json` -> `system_trust_score_artifact.schema.json`
  - `nx_policy_evolution_candidate_set.schema.json` -> `policy_evolution_candidate_set.schema.json`
  - `nx_autonomy_expansion_gate_result.schema.json` -> `autonomy_expansion_gate_result.schema.json`
- `contracts/standards-manifest.json` (example path normalization for these artifact families)
- `spectrum_systems/modules/runtime/nx_governed_system.py` (schema resolver names aligned to canonical filenames)
- `docs/reviews/2026-04-12_fxs_001_schema_manifest_alignment_fix.md`

## 3. Canonical naming decision taken
Adopted manifest-declared `artifact_type` names as canonical schema filenames (`contracts/schemas/<artifact_type>.schema.json`) for the nine affected artifacts. Kept existing `nx_`-prefixed artifact types unchanged where they are explicitly declared as such in the manifest (`nx_review_intelligence_link_artifact`, `nx_roadmap_candidate_artifact`).

## 4. Why this preserves contract discipline
- Bootstrap contract rule remains strict and unchanged.
- Manifest remains the authoritative contract registry.
- Runtime schema resolution now matches canonical contract filenames deterministically.
- No test weakening or special-case bypasses were introduced.

## 5. Tests run and results
- `pytest tests/test_contract_bootstrap.py -q` -> pass (`2 passed`)
- `pytest tests/test_nx_governed_intelligence.py tests/test_nx_governed_system.py -q` -> pass (`15 passed`)
- `pytest tests/test_contracts.py tests/test_contract_enforcement.py -q` -> pass (`117 passed`)
- `python scripts/run_contract_enforcement.py` -> pass (`failures=0 warnings=0 not_yet_enforceable=0`)
