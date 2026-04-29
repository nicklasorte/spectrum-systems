# MET-RT-01 Registry Authority Red-Team

## Prompt type
REVIEW

## Scope
- MET registry entry under `docs/architecture/system_registry.md`
- MET-owned artifacts under `artifacts/dashboard_metrics/`
- MET cockpit blocks under `apps/dashboard-3ls/app/api/intelligence/route.ts`
- PQX candidate action bundles and freeze recommendation signals

## Attack Patterns
1. **MET claiming authority through label drift.**
   - Attack: replace observation language with control verbs (`\`approve_action\``,
     `\`decide_action\``, `\`freeze_action\``, `\`admit_action\``) in MET-owned
     artifacts or dashboard text.
   - Risk: MET silently absorbs CDE/SEL/GOV/AEX authority through wording.

2. **MET shadowing CDE/SEL/GOV via aggregated state.**
   - Attack: cockpit summarises `signal_integrity_check` as a green/red gate
     surface that operators read as authority.
   - Risk: dashboard treats MET aggregate as a closure or freeze observation
     that operators mistake for a CDE/SEL signal.

3. **Action bundles bypassing AEX/PQX.**
   - Attack: `pqx_candidate_action_bundle_record` advertises bundles ready
     for the runtime path without referencing AEX admission.
   - Risk: MET becomes an admission seam.

4. **Freeze signal becoming a SEL enforcement input.**
   - Attack: `met_freeze_recommendation_signal_record` emits "freeze required"
     when SLO budget is unknown.
   - Risk: MET-owned `enforcement_signal` reads as authoritative when the SEL
     `enforcement_action_record` has not yet observed the budget breach.

## Findings

### must_fix
1. **Authority field must remain NONE in registry entry and API block.**
   - Mitigation: registry lists `Authority: NONE` and API exposes
     `authority: 'NONE'` with `forbidden` ownership tokens.

### should_fix
1. Action bundle `readiness_state` must remain `proposed` until AEX produces a
   `build_admission_record`; required_evidence must reference AEX.
2. Freeze signal must remain `no_recommendation` when budget posture is unknown
   and must point at SLO/CDE/SEL — never at MET.

### observation
1. MET cockpit aggregate `overall_integrity_state` is rendered as a warn/ok
   observation, not a control gate.
2. The dashboard MET Cockpit panel does not surface an action button (no
   `Execute`, `\`approve_action\``, or `\`promote_action\`` labels).
