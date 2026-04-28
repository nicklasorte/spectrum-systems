# MET-42 Owner Handoff Authority Red-Team

## Prompt type
REVIEW

## Scope
- owner read observation ledger
- materialization observation mapper
- API/dashboard owner handoff rendering

## Findings

### must_fix
1. **Owner-read rows missing explicit next recommended input in some states.**
   - Attack: candidates without next recommended input.
   - Risk: stale signals cannot retrieve the next artifact path.

### should_fix
1. **Materialization rows should keep stale candidate signal visible with stale window context.**
2. **API block warnings should include missing-artifact path in each unknown degradation branch.**

### observation
1. Owner artifact refs are empty in current sample set; none_observed visibility is preserved.
2. No authority-shaped ownership transfer language detected in the new MET-34/35 artifacts.

