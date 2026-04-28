# MET-32 — Fixes for Red-Team #3 (MET-31)

## Prompt type
FIX

## Scope

Fix every `must_fix` finding from `MET-31-artifact-integrity-redteam.md`.

## Fixes

### Fix F1 — All MET-19-33 paths are classified

- **finding:** New MET-19-33 artifacts must appear in the classification.
- **fix:** `met_generated_artifact_classification_record.json` enumerates
  every MET-19-33 artifact path under `classified_paths[]`. The contract
  test
  `tests/metrics/test_met_19_33_contract_selection.py::test_generated_artifact_classification_covers_met_paths`
  asserts every MET-19-33 file is classified.
- **files changed:**
  - `artifacts/dashboard_metrics/met_generated_artifact_classification_record.json`
  - `tests/metrics/test_met_19_33_contract_selection.py`
  - `apps/dashboard-3ls/__tests__/api/met-19-33-artifacts.test.ts`
- **tests added:**
  - `test_generated_artifact_classification_covers_met_paths`
  - `MET-26 — generated artifact classification covers MET paths` jest
    block
- **residual risk:** None — fail-closed.

### Fix F2 — Missing artifacts degrade to unknown

- **finding:** Vercel must surface `'unknown'` for missing MET artifacts.
- **fix:** Every fail-closed branch in
  `apps/dashboard-3ls/app/api/intelligence/route.ts` for the seven new
  MET-19-33 blocks pins counts to `'unknown'`. The jest test
  `apps/dashboard-3ls/__tests__/api/met-19-33-intelligence.test.ts`
  asserts each unknown.
- **files changed:**
  - `apps/dashboard-3ls/app/api/intelligence/route.ts`
  - `apps/dashboard-3ls/__tests__/api/met-19-33-intelligence.test.ts`
  - `tests/metrics/test_met_19_33_contract_selection.py`
- **tests added:**
  - `test_intelligence_route_does_not_substitute_zero_for_override_evidence_count`
  - `test_intelligence_route_degrades_candidate_closure_to_unknown`
  - `MET-19-33 — /api/intelligence wires new MET fields` block
- **residual risk:** None — every counted field has a unit test.

### Fix F3 — Conflicting generated artifacts cannot be hand-merged

- **finding:** MET dashboard metrics must be regenerated, not hand-merged.
- **fix:**
  `met_generated_artifact_classification_record.json` labels every
  `dashboard_metric` and `derived_metric` path with
  `merge_policy = "regenerate_not_hand_merge"` and every `canonical_seed`
  path with `canonical_review_required`.
- **files changed:**
  - `artifacts/dashboard_metrics/met_generated_artifact_classification_record.json`
  - `tests/metrics/test_met_19_33_contract_selection.py`
- **tests added:**
  - `test_generated_artifact_classification_covers_met_paths` validates
    `merge_policy` is one of the allowed enum values.
- **residual risk:** No `config/generated_artifact_policy.json` exists yet
  to consume this signal centrally; the fold-in will happen when that
  policy lands. Until then MET-26 carries the classification inline.

### Fix F4 — Vercel surfaces dashboard-side warnings

- **finding:** Missing/partial artifacts must surface warnings rather than
  rendering success.
- **fix:** Every new dashboard section maps the block's `warnings[]` to
  `<p className="text-xs text-amber-700">⚠ {w}</p>`. The API envelope
  aggregates per-block warnings into a single list via the existing
  `buildSourceEnvelope` call.
- **files changed:**
  - `apps/dashboard-3ls/app/api/intelligence/route.ts`
  - `apps/dashboard-3ls/app/page.tsx`
  - `apps/dashboard-3ls/__tests__/components/Met19_33Panels.test.tsx`
- **tests added:**
  - `keeps unknown visible when MET-19-33 blocks are missing` jest test
- **residual risk:** Dashboard test mocks return empty payloads to confirm
  the unavailable/unknown text path renders; production payloads must
  retain the same behaviour.

## Residual must_fix items

None. All MET-31 must_fix findings are fixed.
