from __future__ import annotations
import pytest
from spectrum_systems.contracts import load_example, validate_artifact
from spectrum_systems.modules.runtime.integration_fabric_ifb import *


def _roadmap_contract():
    return build_rdx_roadmap_execution_contract(
        roadmap_id='RDX-IFB-001', version='1.0.0', created_at='2026-04-15T01:00:00Z',
        prerequisites=['decision:lin','decision:rep'], required_posture_inputs=['LIN','REP','EVL','EVD','OBS','SLO','CAP'],
        umbrellas=[
            {'umbrella_id':'U1','batches':[{'batch_id':'B1','slices':['S1','S2'],'depends_on':[]},{'batch_id':'B2','slices':['S3','S4'],'depends_on':['B1']}]},
            {'umbrella_id':'U2','batches':[{'batch_id':'B3','slices':['S5','S6'],'depends_on':['B2']},{'batch_id':'B4','slices':['S7','S8'],'depends_on':['B3']}]}])


def test_all_new_examples_validate():
    names=[
'rdx_roadmap_execution_contract','rdx_global_execution_validity_report','rdx_roadmap_contract_diff','rdx_roadmap_prerequisite_graph','rdx_must_revalidate_set','hnx_step_temporal_validity_record','hnx_continuity_drift_report','hnx_forward_validity_projection','hnx_checkpoint_resume_integrity_report','hnx_handoff_completeness_requirement_record','hnx_resume_risk_classification_record','dag_full_roadmap_dependency_validation','dag_critical_path_bottleneck_record','dag_hidden_dependency_suspicion_report','dag_umbrella_boundary_dependency_report','dag_dependency_fanout_risk_record','dep_chain_regression_pack','dep_critical_chain_replay_fixture_pack','dep_post_fix_chain_regression_bundle','crs_cross_phase_consistency_report','crs_consistency_severity_record','crs_contradiction_cluster_record','crs_cross_owner_contradiction_history','lin_full_chain_lineage_report','lin_lineage_decay_report','lin_advancement_lineage_sufficiency_map','rep_replay_after_n_steps_record','rep_replay_window_regression_pack','rep_selective_replay_sampling_policy_record','evl_roadmap_eval_completeness_map','evl_required_eval_debt_record','evl_phase_required_eval_set','evl_red_team_coverage_ledger','evd_roadmap_evidence_sufficiency_map','evd_evidence_thinning_report','evd_step_class_evidence_profile_library','obs_roadmap_observability_completeness_report','obs_trace_correlation_decay_report','obs_missing_signal_provenance_report','obs_gap_to_step_map','prg_signal_prioritization_record','prg_prioritized_control_signal_bundle','prg_roadmap_risk_stack','prg_roadmap_halt_recommendation','prg_roadmap_recut_recommendation','prg_smallest_safe_next_batch_recommendation','ail_correction_pattern_roadmap_candidate_record','ail_trust_posture_trend_delta_record','ail_recurring_exploit_family_record','jdx_judgment_quality_feedback_record','pol_policy_release_performance_record','prx_precedent_reinforcement_record','slo_roadmap_error_budget_posture','slo_roadmap_burn_rate_forecast','slo_roadmap_freeze_threshold_profile','cap_roadmap_capacity_budget_posture','cap_reviewer_load_pressure_record','cap_parallelism_ceiling_record','qos_roadmap_queue_pressure_forecast','qos_retry_storm_susceptibility_record','ctx_roadmap_scale_context_preflight_report','ctx_context_recipe_conformity_report','con_interface_drift_report','con_cross_owner_contract_compatibility_matrix','cde_global_execution_readiness_decision','cde_composite_posture_consumption_contract','cde_invariant_breach_stop_decision','cde_continue_vs_halt_decision','cde_escalation_to_human_decision','ril_plan_wide_coherence_red_team_report','ril_temporal_dependency_red_team_report','ril_signal_overload_red_team_report','ril_budget_readiness_red_team_report']
    for name in names:
        validate_artifact(load_example(name), name)


def test_rdx_contract_and_structure_hooks():
    c=_roadmap_contract()
    assert enforce_rdx_structure_hooks(c, ['decision:lin','decision:rep']) == []
    with pytest.raises(IFBError):
        build_rdx_roadmap_execution_contract(roadmap_id='x',version='1',created_at='2026-04-15T00:00:00Z',prerequisites=[],required_posture_inputs=[],umbrellas=[])


def test_rdx_validity_and_diff_and_hnx_temporal():
    c=_roadmap_contract()
    report=build_rdx_global_execution_validity_report(contract=c, owner_inputs={'LIN':{'created_at':'2026-04-15T00:30:00Z'},'REP':{'created_at':'2026-04-15T00:40:00Z'},'EVL':{'created_at':'2026-04-15T00:50:00Z'},'EVD':{'created_at':'2026-04-15T00:50:00Z'},'OBS':{'created_at':'2026-04-15T00:50:00Z'},'SLO':{'created_at':'2026-04-15T00:50:00Z'},'CAP':{'created_at':'2026-04-15T00:50:00Z'}}, now='2026-04-15T02:00:00Z')
    assert report['status']=='pass'
    diff=build_rdx_roadmap_contract_diff(prior=None, current=c, created_at='2026-04-15T02:00:00Z')
    assert 'missing_prior_contract' in diff['changed_dependencies']
    t=build_hnx_step_temporal_validity_record(step_id='S1', continuity_evidence=['ev:1'], checkpoint_epoch=100, now_epoch=120, max_gap=40)
    assert t['status']=='pass'
    d=build_hnx_continuity_drift_report([t, {**t, 'status':'fail'}])
    assert d['status']=='fail'
    pre=build_rdx_roadmap_prerequisite_graph(contract=c, created_at='2026-04-15T02:00:00Z')
    assert pre['status']=='pass'
    reval=build_rdx_must_revalidate_set(contract_diff=diff, contract=c, created_at='2026-04-15T02:00:00Z')
    assert 'B1' in reval['must_revalidate']


def test_dag_dep_crs_lin_rep_group():
    c=_roadmap_contract()
    dag=build_dag_full_roadmap_dependency_validation(c)
    assert dag['status']=='pass'
    cp=build_dag_critical_path_bottleneck_record(c)
    assert cp['critical_path_length']==4
    dep=build_dep_chain_regression_pack(chain=['B1','B2'], baseline={'B1':'pass','B2':'pass'}, current={'B1':'pass','B2':'fail'})
    assert dep['status']=='fail'
    hidden=build_dag_hidden_dependency_suspicion_report(declared_edges=[('B2','B1')], observed_handoffs=[('B2','B1'),('B3','B9')])
    umb=build_dag_umbrella_boundary_dependency_report(prior_outputs=['o1'], requested_inputs=['o1','o2'], mutation_attempts=['o1'])
    fan=build_dag_dependency_fanout_risk_record(graph={'B1':['B2','B3','B4']})
    fixtures=build_dep_critical_chain_replay_fixture_pack(chains=[['B1','B2'],['B2','B3']])
    post_fix=build_dep_post_fix_chain_regression_bundle(affected_chains=['c1','c2'], rerun_chains=['c1'])
    assert hidden['status']=='warn' and umb['status']=='fail' and fan['status'] in {'warn','pass'}
    assert fixtures['status']=='pass' and post_fix['status']=='fail'
    crs=build_crs_cross_phase_consistency_report(phases={'cert':'pass','replay':'fail'})
    sev=build_crs_consistency_severity_record(inconsistency_code='material', material=True)
    cluster=build_crs_contradiction_cluster_record(contradiction_codes=['x','x','y'])
    hist=build_crs_cross_owner_contradiction_history(events=[{'owner':'CRS','stale':False},{'owner':'REP','stale':True}])
    assert crs['status']=='fail' and sev['status']=='block'
    lin=build_lin_full_chain_lineage_report(chain=['AEX','TLC','TPA','PQX'])
    lin_suf=build_lin_advancement_lineage_sufficiency_map(required_refs=['AEX','PQX'], present_refs=['AEX'])
    rep=build_rep_replay_after_n_steps_record(window_steps=4,replay_passed=True,evidence_refs=['rep:1'])
    sampling=build_rep_selective_replay_sampling_policy_record(required_windows=['w1','w2'], sampled_windows=['w1'])
    assert cluster['status']=='warn' and hist['status']=='warn' and lin_suf['status']=='fail'
    assert lin['status']=='pass' and rep['status']=='pass' and sampling['status']=='fail'


def test_coverage_signals_and_authority_boundaries():
    evl=build_evl_roadmap_eval_completeness_map(['B1','B2'], ['B1'])
    evd=build_evd_roadmap_evidence_sufficiency_map(['B1','B2'], ['B1','B2'])
    obs=build_obs_roadmap_observability_completeness_report(['trace','corr'], ['trace'])
    prio=build_prg_signal_prioritization_record([{'signal_id':'s1','urgency':3,'blast_radius':3,'progression_impact':3},{'signal_id':'s2','urgency':1,'blast_radius':1,'progression_impact':1}])
    bundle=build_prg_prioritized_control_signal_bundle(prio)
    risk=build_prg_roadmap_risk_stack(bundle)
    halt=build_prg_roadmap_halt_recommendation(risk, halt_threshold=10)
    phase_set=build_evl_phase_required_eval_set(['P1','P2'], ['P1'])
    ledger=build_evl_red_team_coverage_ledger(['S1','S2'], ['S1'])
    evd_profile=build_evd_step_class_evidence_profile_library(profiles={'code':['test','review']}, step_class='code')
    obs_missing=build_obs_missing_signal_provenance_report(required_signals=['trace','corr'], observed_signals=['trace'], provenance={'corr':'collector:2'})
    obs_gap=build_obs_gap_to_step_map(['B1','B2'], ['B1'])
    recut=build_prg_roadmap_recut_recommendation(bottlenecks=['B3'])
    smallest=build_prg_smallest_safe_next_batch_recommendation(candidate_batches=[{'batch_id':'B5','risk':4},{'batch_id':'B6','risk':2}])
    assert evl['status']=='fail' and evd['status']=='pass' and obs['status']=='fail'
    assert halt['status']=='halt' and phase_set['status']=='fail' and ledger['status']=='fail'
    assert evd_profile['status']=='pass' and obs_missing['status']=='warn' and obs_gap['status']=='fail'
    assert recut['status']=='candidate_only' and smallest['status']=='candidate_only'


def test_cde_is_only_final_authority_and_umbrella_boundary_decision():
    consume=build_cde_composite_posture_consumption_contract()
    postures={k:{'status':'pass'} for k in consume['required_inputs']}
    read=build_cde_global_execution_readiness_decision(postures=postures, contract=consume)
    stop=build_cde_invariant_breach_stop_decision(material_breaches=[])
    decision=build_cde_continue_vs_halt_decision(readiness=read, stop_decision=stop, umbrella_id='U1')
    escal=build_cde_escalation_to_human_decision(uncertainty=0.8, risk=0.2)
    assert read['owner']=='CDE' and decision['status']=='continue' and escal['status']=='halt'


def test_long_roadmap_synthetic_and_red_team_rounds_with_fix_packs():
    # RT-D1 plan-contract
    rt1=run_red_team_round(round_id='RT-D1', fixtures=[{'fixture_id':'contract-malformed','exploit':True}])
    assert rt1['status']=='fail'
    # FX-D1
    fixed1=build_rdx_roadmap_prerequisite_graph(contract=_roadmap_contract(), created_at='2026-04-15T03:00:00Z')
    assert fixed1['status']=='pass'

    # RT-D2 temporal/dependency
    rt2=run_red_team_round(round_id='RT-D2', fixtures=[{'fixture_id':'tmp-stale','exploit':True}])
    assert rt2['status']=='fail'
    # FX-D2
    fx2=build_hnx_forward_validity_projection(step_id='S9', dependency_count=2, continuity_strength=0.9)
    assert fx2['status']=='pass'

    # RT-D3 coherence/lineage/replay
    rt3=run_red_team_round(round_id='RT-D3', fixtures=[{'fixture_id':'lin-decay','exploit':True}])
    assert rt3['status']=='fail'
    # FX-D3
    fx3=build_lin_advancement_lineage_sufficiency_map(required_refs=['AEX','TLC','TPA','PQX'], present_refs=['AEX','TLC','TPA','PQX'])
    assert fx3['status']=='pass'

    # RT-D4 eval/evidence/observability
    rt4=run_red_team_round(round_id='RT-D4', fixtures=[{'fixture_id':'obs-gap','exploit':True}])
    assert rt4['status']=='fail'
    # FX-D4
    fx4=build_obs_missing_signal_provenance_report(required_signals=['trace'], observed_signals=['trace'], provenance={})
    assert fx4['status']=='pass'

    # RT-D5 signal overload
    rt5=run_red_team_round(round_id='RT-D5', fixtures=[{'fixture_id':'sig-conflict','exploit':True}])
    assert rt5['status']=='fail'
    # FX-D5
    fx5=build_prg_signal_prioritization_record([{'signal_id':'halt-worth','urgency':5,'blast_radius':5,'progression_impact':5}])
    assert fx5['ranked_signals'][0]['signal_id']=='halt-worth'

    # RT-D6 budget/readiness
    rt6=run_red_team_round(round_id='RT-D6', fixtures=[{'fixture_id':'budget-exhausted','exploit':True}])
    assert rt6['status']=='fail'
    # FX-D6
    slo=build_slo_roadmap_error_budget_posture(remaining=0.2)
    cap=build_cap_roadmap_capacity_budget_posture(utilization=0.7)
    qos=build_qos_roadmap_queue_pressure_forecast(queue_depth=8, throughput=4)
    burn=build_slo_roadmap_burn_rate_forecast(consumed=0.2, window_days=10)
    freeze=build_slo_roadmap_freeze_threshold_profile(step_count=100, budget_remaining=0.5)
    rev=build_cap_reviewer_load_pressure_record(reviewers=2, required_reviews=10)
    par=build_cap_parallelism_ceiling_record(requested_parallelism=5, ceiling=4)
    retry=build_qos_retry_storm_susceptibility_record(retries=5, failures=5)
    ctx_pf=build_ctx_roadmap_scale_context_preflight_report(context_tokens=1000, max_tokens=2000, recipe_complete=True)
    ctx_rc=build_ctx_context_recipe_conformity_report(expected_recipe='v1', observed_recipe='v1')
    con_drift=build_con_interface_drift_report(expected_interfaces=['a'], observed_interfaces=['a','b'])
    con_matrix=build_con_cross_owner_contract_compatibility_matrix(pairs=[{'owners':['A','B'],'compatible':False}])
    assert slo['status']=='pass' and cap['status']=='pass' and qos['status'] in {'pass','warn'}
    assert burn['status']=='pass' and freeze['status']=='pass' and rev['status']=='warn'
    assert par['status']=='fail' and retry['status']=='warn' and ctx_pf['status']=='pass' and ctx_rc['status']=='pass'
    assert con_drift['status']=='fail' and con_matrix['status']=='fail'
