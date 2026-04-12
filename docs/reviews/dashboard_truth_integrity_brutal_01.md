# Dashboard Truth Integrity Brutal Review — 01

## 1. Executive Verdict
- **FAIL**

Can this dashboard still lie? **Yes.** The top-level blocked-state gate is stronger than before, but trust still fails at the control boundary: recommendation fallback still invents governance-significant guidance inside UI selectors, and provenance in fallback/non-fallback paths overstates what fields actually drove decisions. Validation improved, but it is still selective and leaves critical publication semantics weak enough that malformed-but-object artifacts can shape labels and integrity messaging.

## 2. Non-Negotiable Findings
- Blocked-state rendering is enforced at the top-level component boundary; operational sections are not rendered when state is not `renderable`.
- Recommendation behavior is **not purely artifact-first**: fallback builds policy guidance from local branch rules (`hardGateUnsatisfied`, `runBlocked`, bottleneck text).
- Recommendation provenance is partially synthetic: fallback provenance points at recommendation artifact even when fallback logic is actually driven by hard gate/run state/bottleneck.
- Provenance key fields for recommendation `source_basis` rows are generic (`source_basis`) rather than the specific evidence fields that drove recommendation text.
- Runtime validation for key artifacts exists, but publication/manifest integrity claims still rely on weakly validated manifest semantics.

## 3. Critical Risks (BLOCKERS)

1. **Selector-level fallback still performs policy interpretation**
   - **File:** `dashboard/lib/selectors/dashboard_selectors.ts`
   - **Exact failure mode:** When recommendation artifact is missing/invalid, selector branches into locally interpreted guidance (`Satisfy hard gate`, `Run bounded repair`, `Address bottleneck`) driven by hard-coded status interpretation.
   - **Why it breaks trust:** UI becomes a policy engine instead of a governed presentation surface.
   - **False operator impression:** Operator can believe recommendation is governed artifact output when it is UI-fabricated control logic.

2. **Fallback provenance does not match actual decision basis**
   - **File:** `dashboard/lib/selectors/dashboard_selectors.ts`
   - **Exact failure mode:** Fallback provenance row references `next_action_recommendation_record.json` even though title/reason are often derived from `hard_gate_status_record.json`, `current_run_state_record.json`, and `current_bottleneck_record.json`.
   - **Why it breaks trust:** Provenance claims precision while omitting real causal artifacts.
   - **False operator impression:** Operator may audit the wrong artifact and believe recommendation logic is artifact-backed when it is branch-backed.

3. **Recommendation provenance field basis is generic, not causal**
   - **File:** `dashboard/lib/selectors/dashboard_selectors.ts`
   - **Exact failure mode:** Non-fallback recommendation provenance maps each `source_basis` path to `keyFields: ['source_basis']` instead of the real fields used to compute user-visible recommendation statements.
   - **Why it breaks trust:** “keys used” signal is decorative, not evidentiary.
   - **False operator impression:** Operator sees a polished provenance table that implies field-level traceability that the selector does not actually implement.

4. **Manifest/publication integrity can be overstated under weak schema checks**
   - **File:** `dashboard/lib/validation/dashboard_validation.ts`
   - **Exact failure mode:** Manifest artifact shape is not discriminator-validated and no strong checks verify required semantics (`required_files` typing/uniqueness, publication contract coherence).
   - **Why it breaks trust:** Labels such as completeness/publication state can be derived from structurally weak inputs.
   - **False operator impression:** Operator may read “complete/live” style integrity labels as contract-grade truth when parser acceptance is still permissive.

## 4. Structural Weaknesses
- Control logic and display logic remain tightly coupled in one selector; future scope additions can quietly reintroduce policy interpretation under the “fallback” umbrella.
- Provenance representation uses hand-authored mappings and token-based assumptions rather than contract-bound field maps, making drift likely as artifacts evolve.
- Artifact family classification in explorer uses filename token matching (`includes('run')`, `includes('gate')`, `includes('recommendation')`), which is fragile under naming drift and easy to silently misclassify.
- Validation coverage is artifact-by-artifact and selective; any new governance-significant artifact defaults to permissive acceptance until someone explicitly adds checks.

## 5. Blocked-State Integrity Assessment
- **Operational rendering gate:** top-level gate is effective; operational surfaces are withheld in blocked states (`no_data`, `incomplete_publication`, `stale`, `truth_violation`).
- **Leakage risk:** direct UI leakage is reduced, but selector still precomputes operationally meaningful recommendation and scorecard structures before renderability is proven. Current component tree hides them, but trust depends on convention plus route layout discipline.
- **Assessment:** safer than before, but not a full structural trust boundary because precomputed operational semantics exist regardless of render gate.

## 6. Manifest / Publication Truth Assessment
- `manifestCompleteness` is derived from declared required files and valid-loaded counts, which is directionally correct.
- Sync/publication labeling is partially anchored to `dashboard_publication_sync_audit.json` validity.
- Remaining overclaim: manifest/sync signals can appear authoritative despite limited schema rigor for manifest semantics and count coherence.
- Declared vs loaded vs missing vs invalid distinction in explorer is materially improved and mostly honest.

## 7. Validation Integrity Assessment
- Validation now rejects malformed fields for several critical artifacts (enum checks, discriminator checks, typed arrays/numbers).
- This is no longer pure theater, but still incomplete as a trust boundary:
  - Manifest contract is under-validated.
  - Many artifacts still pass as generic objects without strict discriminator/field expectations.
  - “Valid” remains uneven across artifact set, so render-gate trust is only as strong as the narrow validated subset.
- **Judgment:** improved but not yet sufficient to be the sole trust boundary for governance-significant UI behavior.

## 8. Recommendation / Control Boundary Assessment
- Primary path is artifact-first when recommendation artifact is present and valid.
- Fallback is explicitly labeled, which is good disclosure.
- However fallback still does governance-significant policy work inside selector branches.
- Status interpretation helpers reduce random token-matching, but UI still interprets what operators should do when recommendation artifact is absent.
- **Conclusion:** control boundary purity is not achieved.

## 9. Provenance Integrity Assessment
- Provenance drawer consistently exposes artifact/path/key fields/timestamps.
- But recommendation provenance remains partly synthetic:
  - Fallback path provenance does not enumerate all causal artifacts.
  - Non-fallback key fields are generic and not tied to actual decision-field extraction.
- **Conclusion:** provenance is improved presentation, not yet reliable evidence.

## 10. Top 5 Surgical Fixes
1. **Kill governance-significant recommendation synthesis in selector fallback.** Restrict fallback to explicit “artifact missing/invalid, no governed recommendation available” with no action prescription.
2. **Make fallback provenance causal.** If any fallback branch references hard gate/run/bottleneck, provenance must enumerate those exact artifacts and fields.
3. **Enforce strict manifest validation.** Validate manifest discriminator, required file list type, uniqueness, and coherence with sync audit count.
4. **Replace token-based artifact family classification with declared contract metadata.** Remove filename heuristic branching for governance-relevant categorization.
5. **Fail closed on provenance field uncertainty.** If actual decision fields are unknown, label as unknown explicitly instead of emitting generic key placeholders.

## 11. Next Hard Gate
- **Checkpoint name:** `DASHBOARD_TRUTH_BOUNDARY_GATE_V1`
- **Required pass criteria:**
  1. Recommendation fallback contains zero prescriptive policy logic.
  2. Recommendation provenance is causal in both artifact-backed and fallback modes.
  3. Manifest + sync audit validation rejects malformed or incoherent publication contract inputs.
  4. No governance-significant classifier in selectors depends on filename/status heuristics.

Until this gate passes, expanding dashboard scope increases trust debt faster than capability.
