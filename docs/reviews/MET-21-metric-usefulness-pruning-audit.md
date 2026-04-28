# MET-21 — Metric Usefulness + Pruning Audit

## Prompt type
AUDIT

## Scope

This audit reviews every MET-owned artifact, every MET API field exposed via
`/api/intelligence`, every MET dashboard panel, and every MET-bound test for
whether it justifies itself by **failure_prevented** or **signal_improved**.

Per the MET-19-33 charter, MET observes, measures, explains, and recommends.
MET does not decide, approve, enforce, certify, promote, execute, or admit.
This audit recommends keep / fold / remove dispositions only; canonical owners
adopt or reject those recommendations.

## Audit table — MET artifacts

|name|type|failure_prevented|signal_improved|keep/fold/remove|reason|dependency impact|recommended simplification|
|---|---|---|---|---|---|---|---|
|`bottleneck_record.json`|artifact|Bottleneck staying invisible during promotion review|Dominant constrained leg + supporting evidence + confidence rationale|keep|Single sourced handle for the constrained-leg observation|consumed by `bottleneck` API block and OC bottleneck panel|none — already compact|
|`leverage_queue_record.json`|artifact|Items competing without a sourced ranking|Items carry leverage_score + source_artifacts_used + systems_affected|keep|Sole MET ranking artifact; no overlap|consumed by `leverage_queue` API block, Overview panel D, Roadmap tab|none|
|`risk_summary_record.json`|artifact|Risk posture inferred from disparate seed artifacts|fallback/unknown counts + proof_chain_coverage in one place|keep|Single risk rollup; not duplicated|consumed by `risk_summary` API block|none|
|`failure_feedback_record.json`|artifact|Failures/near misses unobserved into next loop|Each failure linked to feedback item with affected_systems|keep|Source-of-truth for feedback ledger|consumed by `feedback_items` API block; closure ledger references it|none|
|`eval_candidate_record.json`|artifact|Eval coverage gaps remaining unowned|Each gap has owner_recommendation=EVL with input artifacts|keep|Primary EVL handoff record|consumed by `eval_candidates` API block; closure ledger references candidate IDs|none|
|`policy_candidate_signal_record.json`|artifact|Policy gaps without a named candidate signal|Signals carry suggested_owner_system + required_evidence_before_adoption|keep|Primary canonical-owner handoff record|consumed by `policy_candidate_signals`|none|
|`feedback_loop_snapshot.json`|artifact|Loop status read from disparate artifacts|Single rollup of counts + themes + next_recommended_improvement_inputs|keep|First-stop overview rollup|consumed by `feedback_loop`|none|
|`failure_explanation_packets.json`|artifact|Operators needing >15 min to answer what/why/where/source/next|Per-failure packet with what_failed, evidence, next_recommended_input|keep|Direct precursor to MET-25 debug explanation index|consumed by `failure_explanation_packets`|MET-25 builds on it; the index does not replace per-failure packets|
|`override_audit_log_record.json`|artifact|Override count silently reported as 0|Override count remains unknown until canonical log exists|fold_candidate|MET-24 `override_evidence_intake_record` carries a richer evidence_status field|consumed by `override_audit`|Once MET-24 is read by SEL/CDE, fold this artifact's downstream wiring into MET-24. Until then, keep both since closure ledger references this record.|
|`eval_materialization_path_record.json`|artifact|EVL handoff implicit with no required-input list|Materialization path is proposed only with required_authority_inputs|fold_candidate|MET-23 `evl_handoff_observation_tracker_record` subsumes per-candidate handoff observations|consumed by `eval_materialization_path`|Once MET-23 is read by EVL, fold this artifact. Keep for now to preserve EVL-handoff history.|
|`replay_lineage_hardening_record.json`|artifact|Causality gaps with no record naming missing dimensions/edges|Per-dimension status + per-edge lineage status|keep|Sole MET artifact tracking REP/LIN per-dimension/edge gaps|consumed by `replay_lineage_hardening`|none|
|`fallback_reduction_plan_record.json`|artifact|Stub fallback rows reported as artifact-backed|Per-row replacement_signal_needed + priority|keep|Single registry for high-leverage fallback rows|consumed by `fallback_reduction_plan`|none|
|`sel_compliance_signal_input_record.json`|artifact|Observe-only posture read as passivity|Compliance signal input proposes first-class compliance_posture field|keep|Single SEL-targeted compliance signal input record|consumed by `sel_compliance_signal_input`|none|
|`candidate_closure_ledger_record.json` (MET-19, new)|artifact|Candidates accumulating as a stale suggestion pile|Per-candidate age_days + stale_after_days + current_state|keep|Sole closure tracker across candidate types|consumed by new `candidate_closure` block|none|
|`met_artifact_dependency_index_record.json` (MET-20, new)|artifact|New engineer cannot answer what reads each MET artifact under 15 min|Per-artifact upstream/downstream + debug_question_answered|keep|Sole MET debug map|consumed by new `met_artifact_dependency_index` block|none|
|`trend_frequency_honesty_gate_record.json` (MET-22, new)|artifact|Fake trend declared below comparable_case threshold|`cases_needed` is explicit, trend_state stays unknown|keep|Sole gate against fake-trend rendering|consumed by new `trend_frequency_honesty_gate` block|none|
|`evl_handoff_observation_tracker_record.json` (MET-23, new)|artifact|EVL bottleneck unaddressed; per-candidate handoff invisible|Per-handoff signal with materialization_observation|keep|Sole EVL handoff tracker; subsumes MET-09 (fold_candidate)|consumed by new `evl_handoff_observations` block|once EVL reads it, fold MET-09 wiring|
|`override_evidence_intake_record.json` (MET-24, new)|artifact|Override count silently reported as 0; intake shape ambiguous|`evidence_status` + `override_evidence_count` honest unknown|keep|Sole intake-ready override evidence shape|consumed by new `override_evidence_intake` block|once SEL/CDE read it, fold MET-06 (override_audit_log) downstream wiring|
|`debug_explanation_index_record.json` (MET-25, new)|artifact|Operators needing >15 min for failure → evidence → candidate → next|Per-explanation entry with debug_readiness label|keep|Sole MET 15-minute debug index|consumed by new `debug_explanation_index` block|MET-05 packets remain per-failure; index aggregates|
|`met_generated_artifact_classification_record.json` (MET-26, new)|artifact|Generated MET paths unclassified for merge policy|Per-path classification + merge_policy|keep|Sole MET artifact aligning with generated-artifact policy|consumed by new `met_generated_artifact_classification` block|none|

## Audit table — API fields (`/api/intelligence`)

|name|type|failure_prevented|signal_improved|keep/fold/remove|reason|dependency impact|
|---|---|---|---|---|---|---|
|`bottleneck`|api_field|Bottleneck invisible|Constrained leg explicit|keep|Single MET signal for OC panel|—|
|`leverage_queue`|api_field|Unsourced ranking|Sourced leverage list|keep|Powers Overview D|—|
|`risk_summary`|api_field|Risk posture invisible|Fallback/unknown counts visible|keep|Powers Trust Pulse|—|
|`feedback_items`|api_field|Feedback unowned|Per-item failure_prevented/signal|keep|Powers Learning Loop|—|
|`eval_candidates`|api_field|Eval gaps unowned|Per-candidate input + owner|keep|Powers Learning Loop|—|
|`policy_candidate_signals`|api_field|Policy gaps unowned|Per-signal owner + evidence|keep|Powers Learning Loop|—|
|`feedback_loop`/`feedback_loop_status`/`unresolved_feedback_count`|api_field|Loop status dispersed|Single rollup|keep|Powers Learning Loop summary|—|
|`failure_explanation_packets`|api_field|Operator >15 min debug|Per-failure packet|keep|Powers Failure Explanation panel|—|
|`override_audit`|api_field|Override silently 0|override_count remains unknown|fold_candidate|MET-24 `override_evidence_intake` carries richer shape|once MET-24 wired, fold|
|`eval_materialization_path`|api_field|Implicit EVL handoff|Materialization proposed only|fold_candidate|MET-23 `evl_handoff_observations` carries per-candidate handoff|once MET-23 wired, fold|
|`additional_cases_summary`|api_field|Trend declared with <3 cases|case_count + trend honesty|keep — but folded into MET-22 honesty gate read|MET-22 `trend_frequency_honesty_gate` gates the trend label|once MET-22 wired, the trend label is read from MET-22|
|`replay_lineage_hardening`|api_field|Per-dimension/edge gaps unobserved|Per-dimension/edge status|keep|Powers Replay+Lineage panel|—|
|`fallback_reduction_plan`|api_field|Stub fallback as artifact-backed|Per-row replacement signal|keep|Powers Fallback Reduction panel|—|
|`sel_compliance_signal_input`|api_field|Observe-only as passivity|Compliance signal input|keep|—|—|
|`candidate_closure` (new)|api_field|Stale candidate pile invisible|Per-candidate age + stale_after|keep|Powers Candidate Closure panel|—|
|`met_artifact_dependency_index` (new)|api_field|Debug map invisible to API|Per-artifact upstream/downstream|keep|Read-only debug surface|—|
|`trend_frequency_honesty_gate` (new)|api_field|Fake trend label|cases_needed + blocked_trend_fields|keep|Powers Trend Honesty panel|—|
|`evl_handoff_observations` (new)|api_field|EVL handoff invisible|Per-handoff materialization observation|keep|Powers EVL Handoff panel|—|
|`override_evidence_intake` (new)|api_field|Pure override blindness|evidence_status absent/partial/present|keep|Powers Artifact Integrity (override) panel|—|
|`debug_explanation_index` (new)|api_field|Operator >15 min debug|Per-explanation debug_readiness|keep|Powers Debug Explanation panel|—|
|`met_generated_artifact_classification` (new)|api_field|Unclassified generated paths|Per-path classification|keep|Powers Artifact Integrity panel|—|

## Audit table — Dashboard panels

|name|type|failure_prevented|signal_improved|keep/fold/remove|reason|recommended simplification|
|---|---|---|---|---|---|---|
|A. Trust Pulse|dashboard_panel|trust posture invisible|artifact-backed % visible|keep|core operator surface|none|
|B. Simple 3LS Flowchart|dashboard_panel|loop topology invisible|canonical loop visible|keep|core operator surface|none|
|C. Top 3 Recommendations|dashboard_panel|next-bundle invisible|TLS-sourced ranking|keep|core operator surface|none|
|D. Leverage Queue|dashboard_panel|leverage queue invisible|top-3 leverage visible|keep|compact, top-3 only|none|
|E. Explain System State|dashboard_panel|root cause invisible|deterministic root cause|keep|conditional render only|none|
|F. Learning Loop|dashboard_panel|candidates unowned|loop counts + themes|keep|compact|none|
|G. Failure Explanation|dashboard_panel|operator >15 min debug|per-failure packets|keep|compact|none|
|H. Override / Unknowns|dashboard_panel|override silently 0|reason_codes visible|keep|compact|MET-19-33 wires it to override_evidence_intake when MET-24 lands|
|I. Fallback Reduction|dashboard_panel|stub fallback hidden|high-leverage rows|keep|compact|none|
|J. Replay + Lineage Hardening|dashboard_panel|gaps invisible|per-dim/edge status|keep|compact|none|
|K. Candidate Closure (MET-19, new)|dashboard_panel|stale candidate pile invisible|age + stale_after visible|keep|compact, top 3–5 items|none|
|L. Debug Explanation Index (MET-25, new)|dashboard_panel|operator >15 min debug|per-explanation debug_readiness|keep|compact|none|
|M. Trend/Frequency Honesty (MET-22, new)|dashboard_panel|fake trend rendered|cases_needed visible|keep|compact|none|
|N. EVL Handoff Observations (MET-23, new)|dashboard_panel|EVL handoff invisible|per-handoff materialization observation|keep|compact|none|
|O. Artifact Integrity (MET-26, new)|dashboard_panel|generated paths unclassified|per-path classification|keep|compact|none|

## Audit table — Tests

|name|type|failure_prevented|signal_improved|keep/fold/remove|reason|
|---|---|---|---|---|---|
|`tests/metrics/test_met_04_18_contract_selection.py`|test|MET-04-18 contract drift undetected|pytest selection covers MET-04-18 paths|keep|binding selection target|
|`apps/dashboard-3ls/__tests__/api/met-04-18-intelligence.test.ts`|test|API drift undetected|MET-04-18 blocks asserted|keep|binding API contract|
|`apps/dashboard-3ls/__tests__/api/met-04-18-learning-loop.test.ts`|test|Learning-loop schema drift undetected|envelope + invariants asserted|keep|binding artifact contract|
|`apps/dashboard-3ls/__tests__/components/Met04Panels.test.tsx`|test|UI regression undetected|MET-04-18 sections asserted|keep|binding UI contract|
|`tests/metrics/test_met_19_33_contract_selection.py` (new)|test|MET-19-33 contract drift undetected|pytest selection covers MET-19-33 paths|keep|new binding selection target|

## Decision rule

If an artifact, API field, dashboard panel, or test prevents no named failure
and improves no measurable signal, the audit recommends fold or remove.

Per the MET-19-33 charter, no existing artifact is removed in this PR unless
the red-team identifies a newly added MET-19-33 artifact as redundant and
marks it must_fix. fold_candidate items remain in place; their downstream
wiring will be folded once the canonical owner adopts the replacement.

## Authority neutrality

This audit is an MET observation. It recommends keep/fold/remove dispositions
only. Canonical owners (EVL/TPA/CDE/SEL/GOV) adopt or reject the
recommendations through their own governed flows.
