# MET-RT-05 Debuggability Red-Team

## Prompt type
REVIEW

## Scope
- `operator_debuggability_drill_record`
- `time_to_explain_record`
- `debug_readiness_sla_record`
- `failure_explanation_packets`
- `counterfactual_reconstruction_record`
- `earlier_intervention_signal_record`

## Attack Patterns
1. **Failure not explainable in 15 minutes.**
   - Attack: drill items lack one or more of the canonical six questions.
   - Risk: operators cannot reconstruct what failed.

2. **Missing source evidence.**
   - Attack: explanation entries reference a packet but provide no
     source_evidence array.
   - Risk: claims become unverifiable.

3. **Next input unclear.**
   - Attack: explanation states "fix this" without an artifact-backed
     `next_recommended_input`.
   - Risk: operators cannot proceed.

4. **Invented earlier intervention.**
   - Attack: counterfactual entry states "we would have intervened at X"
     without artifact evidence.
   - Risk: postmortems become creative writing.

## Findings

### must_fix
1. **Every drill item must answer the canonical six questions.**
2. **Counterfactual entries must cite artifact-backed evidence; unknown
   stays unknown.**
3. **Debug readiness SLA states must be one of sufficient / partial /
   insufficient / unknown.**

### should_fix
1. Time-to-explain entries surface `questions_remaining` so operators see
   what is missing.
2. Earlier-intervention signal entries reference the earliest artifact and
   the recommended owner system.

### observation
1. Today's drill is partial; debug readiness for GOV-fallback drills is
   unknown until DRILL-GOV-FALLBACK-001 is authored.
2. Counterfactual entry CF-CDE-OVERRIDE-AUDIT is `unknown` — no invented
   history.
