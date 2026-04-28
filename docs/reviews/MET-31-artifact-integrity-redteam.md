# MET-31 — Red-Team #3: Artifact Integrity

## Prompt type
RED-TEAM

## Scope

Attacks against MET-19-33 artifact integrity, generated-artifact handling,
and dashboard freshness.

## Attack surface

- Hand-merged generated state masking regeneration drift.
- Stale generated artifacts being read by the dashboard without warning.
- Conflicting generated artifacts producing inconsistent operator views.
- Missing regeneration path for new artifacts.
- Unclassified MET artifact paths slipping past merge policy.
- Vercel/dashboard rendering stale metrics without warning.

## Findings

### F1 — must_fix — All MET dashboard_metrics paths are classified
**finding:** New MET-19-33 artifacts must appear in
`met_generated_artifact_classification_record.json`.
**evidence:**
`tests/metrics/test_met_19_33_contract_selection.py::test_generated_artifact_classification_covers_met_paths`
asserts every MET-19-33 file path is classified.
**risk if unfixed:** Hand-merge regression on new paths.

### F2 — must_fix — Missing artifacts degrade to unknown, never zero
**finding:** Vercel reading a missing MET artifact must surface
`'unknown'`, not a synthetic 0 or PASS.
**evidence:** `apps/dashboard-3ls/app/api/intelligence/route.ts` fail-closed
branches expose `'unknown'` for `override_evidence_count`,
`candidate_item_count`, `stale_candidate_signal_count`, `cases_needed`,
`trend_state`, `frequency_state`, `handoff_item_count`,
`explanation_entry_count`, and `classified_path_count` when the artifact is
missing. Each missing-artifact branch carries a warning naming the file.
**risk if unfixed:** Dashboard reads zero as healthy.

### F3 — must_fix — Conflicting generated artifacts cannot be hand-merged
**finding:** MET dashboard metrics must be regenerated, not hand-merged.
**evidence:** `met_generated_artifact_classification_record.json`
classifies every dashboard_metric path with
`merge_policy = "regenerate_not_hand_merge"`. Canonical seed paths are
labelled `canonical_review_required`.
**risk if unfixed:** Conflict-merge drift.

### F4 — must_fix — Vercel must surface dashboard-side warnings
**finding:** When MET artifacts are missing or partial, the dashboard must
surface warnings rather than render success.
**evidence:** Each new dashboard panel renders the block's `warnings[]` and
the API envelope aggregates per-block warnings into a single warning list.
**risk if unfixed:** Operator sees a clean dashboard hiding a missing
artifact.

### F5 — should_fix — Dependency index records downstream consumers
**finding:** Per-artifact downstream consumer lists let an operator answer
"who reads this".
**evidence:**
`met_artifact_dependency_index_record.json::artifact_dependencies[]`
records `downstream_consumers` for every MET artifact.
**risk if unfixed:** Debug map missing one direction.

### F6 — observation — No `config/generated_artifact_policy.json` exists yet
**observation:** The repo does not currently carry
`config/generated_artifact_policy.json` or
`docs/generated-artifact-merge-policy.md`. MET-26 records its
classification inline and notes the absence in `reason_codes` and
`warnings`. If a generated-artifact policy file lands later, MET will read
from it rather than carrying classification inline.

### F7 — observation — Stale-content detection lives outside MET
**observation:** Detecting whether a dashboard metric is stale (i.e., older
than the artifact it summarizes) is a freshness signal owned by OBS/REP.
MET surfaces the artifact's `created_at` field but does not produce a
freshness_signal of its own.

## Classification summary

|severity|count|
|---|---|
|must_fix|4|
|should_fix|1|
|observation|2|

## Routing

All must_fix findings are addressed in
`MET-32-artifact-integrity-fixes.md`.
