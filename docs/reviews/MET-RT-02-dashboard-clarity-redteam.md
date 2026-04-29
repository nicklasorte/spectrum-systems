# MET-RT-02 Dashboard Clarity Red-Team

## Prompt type
REVIEW

## Scope
- MET Cockpit panel in `apps/dashboard-3ls/app/page.tsx`
- Top-3 next inputs surface
- Owner handoff queue surface
- Outcome attribution / calibration / recurrence / integrity surfaces

## Attack Patterns
1. **Cockpit clutter hiding the top fix.**
   - Attack: surface every MET artifact as a separate full table on the
     overview tab; operators cannot identify the next safe action.
   - Risk: top recommendation gets lost in the noise.

2. **Weak loop leg unclear.**
   - Attack: hide `weakest_loop_leg` behind a secondary tab; cockpit shows
     only aggregate counts.
   - Risk: operators do not know which leg is constrained.

3. **Authority verbs leaking onto buttons.**
   - Attack: add an action button (`Execute`, `\`approve_action\``,
     `\`promote_action\``) to the cockpit.
   - Risk: dashboard becomes an authority surface for MET.

## Findings

### must_fix
1. **MET Cockpit must answer the five required questions in compact form.**
   - Trust observation, weakest loop leg, top 3 inputs, owner handoff queue,
     stale candidate pressure, outcome / confidence / recurrence / debug /
     integrity — all visible on the overview tab.

### should_fix
1. Compact cards capped to MET_COMPACT_ITEM_MAX (5) rendered items per
   section; full detail stays in artifacts.
2. Each card cites `source_artifacts_used`.

### observation
1. Cockpit has no Execute button; surface remains observation-only.
2. Authority is rendered explicitly as "NONE" alongside the registry status.
