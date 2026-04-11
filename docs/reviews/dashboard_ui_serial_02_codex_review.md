# Dashboard UI Codex Review — SERIAL-02

## 1. Executive Summary
- **FAIL**
- The dashboard still contains multiple trust-breaking paths: policy-significant recommendation behavior is still synthesized in selector heuristics, runtime validation remains shallow enough for malformed artifacts to pass, and provenance metadata still uses placeholder key-basis rows that can mislead operators. Render suppression at the top level is improved, but truth and provenance integrity are not structurally enforced end-to-end.

## 2. Verified Strengths
- Top-level render suppression is now explicit: `RepoDashboard` blocks `DashboardSections` for `no_data`, `incomplete_publication`, `stale`, and `truth_violation`.
- Render state determination is centralized in `deriveRenderState` and includes manifest coverage, source-live gate, and freshness gate in deterministic order.
- `next_action_recommendation_record.json` is explicitly loaded in the publication loader and used as the primary recommendation source when present and valid.
- Explorer status taxonomy now distinguishes declared-loaded-valid, declared-not-loaded, declared-missing, and loaded-invalid states.

## 3. Critical Risks (BLOCKERS)
- **Selector-embedded policy logic remains active.** Recommendation generation still encodes policy-like decisions using token heuristics (`truthyStatus`, `blockedStatus`) and local branch logic (`hardGateUnsatisfied`, `runBlocked`, bottleneck fallback), allowing governance-significant behavior without contract-backed policy interpretation.
- **Validation integrity is insufficient for critical artifacts.** Most artifacts pass if they are objects; discriminator checks only cover a small subset and do not validate field types/enums/shape depth. Malformed artifact bodies can still be treated as valid and influence view-model derivation.
- **Provenance truth is partially synthetic.** Global provenance uses placeholder `keysUsed: ['artifact-backed']` for every artifact, and recommendation provenance can emit generic `recommendation_source_n` rows rather than canonical artifact identity. This weakens trust in drawer claims.
- **Publication integrity can be overstated by count mismatch semantics.** `manifestCompleteness` compares valid loaded count against manifest `artifact_count` even when `artifact_count` may diverge from `required_files.length`; this can produce misleading completeness messaging.

## 4. Structural Weaknesses
- `syncAuditState` is displayed as `manifest:<publication_state>` and is not actually derived from `dashboard_publication_sync_audit.json`, despite the label implying sync-audit semantics.
- `runtime_hotspots` is read after gate computation in `RepoDashboard`; while not rendered, this remains an unnecessary pre-renderable operational read.
- Family classification in artifact explorer is token-based (`name.includes(...)`) and can drift as filenames evolve.
- Tests are source-string assertions; they confirm literal code presence but not runtime behavior under malformed or adversarial artifact payloads.

## 5. Render Integrity Assessment
- **Blocked-state suppression:** Top-level suppression is correct in `RepoDashboard`; operational sections are not rendered when state is non-renderable.
- **Gated reads:** Most operational render paths are gated, but not all data access is strictly post-gate (`runtime_hotspots` extraction happens before branch render).
- **Render-state correctness:** Guard ordering is generally sound (`incomplete_publication` before source-live and stale), but correctness depends on weak artifact validation and manifest assumptions.

## 6. Manifest / Publication Truth Assessment
- **Completeness:** Partially improved but still fragile due to reliance on `artifact_count` semantics and lack of strict schema enforcement.
- **Publication state:** `publicationState` and `syncAuditState` both derive from manifest publication state; true sync-audit artifact semantics are not represented.
- **Loaded vs declared coverage:** Explorer status now distinguishes major states, including invalid loaded and declared-not-loaded.
- **Risk of implied full coverage:** UI can still imply stronger integrity than proven because validity checks are shallow and provenance key-basis is synthetic.

## 7. Recommendation / Provenance Assessment
- **Recommendation source:** Primary source is correctly `next_action_recommendation_record.json` when valid.
- **Fallback labeling:** Fallback recommendation paths are marked with `synthesizedFallback: true`, which is good.
- **Provenance correctness:** Not fully trustworthy. Recommendation provenance rows can be generic and global provenance key usage is placeholder-like, reducing evidence fidelity.

## 8. Control Boundary Assessment
- Selector still performs governance-significant control interpretation through local heuristics (`truthyStatus`, `blockedStatus`) and recommendation branching.
- This keeps policy/control behavior embedded in UI-side selection instead of artifact/contracts.
- Governance-significant behavior is therefore convention-enforced, not structurally enforced.

## 9. Top 5 Surgical Fixes
1. Replace `truthyStatus`/`blockedStatus` token heuristics with contract-backed normalized status enums from artifacts.
2. Expand `validateArtifactShape` for critical artifacts to enforce required discriminator fields **and** field type/enum checks (not object-only validity).
3. Make provenance drawers emit artifact-accurate `keysUsed` and canonical artifact identity; remove placeholder `artifact-backed` basis.
4. Derive `syncAuditState` from actual sync-audit artifact (`dashboard_publication_sync_audit.json`) or relabel field to avoid false implication.
5. Remove ungated operational reads (e.g., `runtime_hotspots`) from pre-renderable paths and enforce access through a single renderable-only accessor.

## 10. Recommended Next Hard Gate
- **Checkpoint:** `DASHBOARD-TRUTH-INTEGRITY-GATE-01`
- **Pass criteria:**
  - No selector-side token heuristics for governance-significant decisions.
  - Critical artifact validation rejects malformed payloads beyond object checks.
  - Provenance drawers use real artifact names/paths/fields actually consulted by derivation logic.
  - Sync/publication integrity labels map to the actual artifact that backs them.
