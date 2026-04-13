# DASHBOARD-NEXT-75-SERIAL-05 Fix Handoff

Use this narrow follow-up prompt only for remaining blockers/highest-leverage surgical fixes:

1. Add artifact-specific row compilers for top 10 highest-risk serial-05 panels (`promotion_failure`, `certification_failure`, `replay_mismatch_root_cause`, `review_debt`, `route_canary`, `model_tournament`, `slice_severity`, `panel_materiality_ranking`, `panel_retirement_candidate`, `link_integrity`).
2. Keep all logic observational and read-only.
3. Preserve fail-closed behavior for unknown/unmapped values.
4. Do not introduce new systems or ownership overlaps.
5. Re-run dashboard build + repo pytest + serial-05 tests.
