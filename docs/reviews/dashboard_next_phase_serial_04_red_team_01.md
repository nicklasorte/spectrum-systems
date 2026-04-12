# DASHBOARD NEXT PHASE SERIAL 04 — Red Team Review 01

## Scope
Review for shadow decisioning, evidence overclaim, export misuse, ranking misuse, and hidden authority drift.

## Blockers
1. Escalation wording could be misread as actual control decision unless explicitly separated from decision artifact.
2. Evidence gap and override hotspot surfaces needed stronger drill-down references to source artifact fields.

## Top 5 Surgical Fixes
1. Add explicit `approaching_threshold_only` and `decision_artifact_separate` labels in escalation rows.
2. Add `materiality_score` row with basis field in evidence gap hotspots.
3. Require fail-closed block for missing change conditions rather than permissive empty rendering.
4. Add governed export `projection_only` hard check before render.
5. Add operator coordination grouping rows with explicit `read_only` boundary annotations.
