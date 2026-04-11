# RVW-DASHBOARD-DATA-SHAPE-FIX-01

## Prompt type
REVIEW

## Scope
`dashboard/components/RepoDashboard.tsx`

## Review answers
1. **Does the dashboard now match the snapshot contract?**
   - Yes. Snapshot typing now matches the artifact contract fields for `root_counts`, `core_areas`, `constitutional_center`, `runtime_hotspots`, and `operational_signals`.

2. **Are counts correct?**
   - Yes. The repository snapshot card now uses `files_total`, `runtime_modules`, `tests`, and `contracts_total`, and also shows `docs` and `run_artifacts`.

3. **Do hotspots and signals render correctly?**
   - Yes. Runtime hotspots now render as object fields (`area`, `count`, `note`) and operational signals render as object fields (`title`, `status`, `detail`).

4. **Was the fix surgical and non-disruptive?**
   - Yes. The change is constrained to snapshot data shape typing, fallback keys, and rendering logic for the two affected panels while preserving layout and fetch behavior.

## Verdict
**DATA SHAPE FIX READY**
