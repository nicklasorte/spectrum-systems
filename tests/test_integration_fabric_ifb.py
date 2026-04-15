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
'rdx_roadmap_execution_contract','rdx_global_execution_validity_report','rdx_roadmap_contract_diff','hnx_step_temporal_validity_record','hnx_continuity_drift_report','hnx_forward_validity_projection','dag_full_roadmap_dependency_validation','dag_critical_path_bottleneck_record','dep_chain_regression_pack','crs_cross_phase_consistency_report','crs_consistency_severity_record','lin_full_chain_lineage_report','lin_lineage_decay_report','rep_replay_after_n_steps_record','rep_replay_window_regression_pack','evl_roadmap_eval_completeness_map','evl_required_eval_debt_record','evd_roadmap_evidence_sufficiency_map','evd_evidence_thinning_report','obs_roadmap_observability_completeness_report','obs_trace_correlation_decay_report','prg_signal_prioritization_record','prg_prioritized_control_signal_bundle','prg_roadmap_risk_stack','prg_roadmap_halt_recommendation','ail_correction_pattern_roadmap_candidate_record','ail_trust_posture_trend_delta_record','jdx_judgment_quality_feedback_record','pol_policy_release_performance_record','prx_precedent_reinforcement_record','slo_roadmap_error_budget_posture','cap_roadmap_capacity_budget_posture','qos_roadmap_queue_pressure_forecast','cde_global_execution_readiness_decision','cde_composite_posture_consumption_contract','cde_invariant_breach_stop_decision','cde_continue_vs_halt_decision','ril_plan_wide_coherence_red_team_report','ril_temporal_dependency_red_team_report','ril_signal_overload_red_team_report','ril_budget_readiness_red_team_report']
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


def test_dag_dep_crs_lin_rep_group():
    c=_roadmap_contract()
    dag=build_dag_full_roadmap_dependency_validation(c)
    assert dag['status']=='pass'
    cp=build_dag_critical_path_bottleneck_record(c)
    assert cp['critical_path_length']==4
    dep=build_dep_chain_regression_pack(chain=['B1','B2'], baseline={'B1':'pass','B2':'pass'}, current={'B1':'pass','B2':'fail'})
    assert dep['status']=='fail'
    crs=build_crs_cross_phase_consistency_report(phases={'cert':'pass','replay':'fail'})
    sev=build_crs_consistency_severity_record(inconsistency_code='material', material=True)
    assert crs['status']=='fail' and sev['status']=='block'
    lin=build_lin_full_chain_lineage_report(chain=['AEX','TLC','TPA','PQX'])
    rep=build_rep_replay_after_n_steps_record(window_steps=4,replay_passed=True,evidence_refs=['rep:1'])
    assert lin['status']=='pass' and rep['status']=='pass'


def test_coverage_signals_and_authority_boundaries():
    evl=build_evl_roadmap_eval_completeness_map(['B1','B2'], ['B1'])
    evd=build_evd_roadmap_evidence_sufficiency_map(['B1','B2'], ['B1','B2'])
    obs=build_obs_roadmap_observability_completeness_report(['trace','corr'], ['trace'])
    prio=build_prg_signal_prioritization_record([{'signal_id':'s1','urgency':3,'blast_radius':3,'progression_impact':3},{'signal_id':'s2','urgency':1,'blast_radius':1,'progression_impact':1}])
    bundle=build_prg_prioritized_control_signal_bundle(prio)
    risk=build_prg_roadmap_risk_stack(bundle)
    halt=build_prg_roadmap_halt_recommendation(risk, halt_threshold=10)
    assert evl['status']=='fail' and evd['status']=='pass' and obs['status']=='fail'
    assert halt['status']=='halt'


def test_cde_is_only_final_authority_and_umbrella_boundary_decision():
    consume=build_cde_composite_posture_consumption_contract()
    postures={k:{'status':'pass'} for k in consume['required_inputs']}
    read=build_cde_global_execution_readiness_decision(postures=postures, contract=consume)
    stop=build_cde_invariant_breach_stop_decision(material_breaches=[])
    decision=build_cde_continue_vs_halt_decision(readiness=read, stop_decision=stop, umbrella_id='U1')
    assert read['owner']=='CDE' and decision['status']=='continue'


def test_long_roadmap_synthetic_and_red_team_rounds_with_fix_packs():
    # RT-C1 coherence
    rt1=run_red_team_round(round_id='RT-C1', fixtures=[{'fixture_id':'coh-1','exploit':True}])
    assert rt1['status']=='fail'
    # FX-C1
    fixed1=build_crs_cross_phase_consistency_report(phases={'cert':'pass','replay':'pass'})
    assert fixed1['status']=='pass'

    # RT-C2 temporal/dependency
    rt2=run_red_team_round(round_id='RT-C2', fixtures=[{'fixture_id':'tmp-1','exploit':True}])
    assert rt2['status']=='fail'
    # FX-C2
    fx2=build_hnx_forward_validity_projection(step_id='S9', dependency_count=2, continuity_strength=0.9)
    assert fx2['status']=='pass'

    # RT-C3 signal overload
    rt3=run_red_team_round(round_id='RT-C3', fixtures=[{'fixture_id':'sig-1','exploit':True}])
    assert rt3['status']=='fail'
    # FX-C3
    fx3=build_prg_signal_prioritization_record([{'signal_id':'halt-worth','urgency':5,'blast_radius':5,'progression_impact':5}])
    assert fx3['ranked_signals'][0]['signal_id']=='halt-worth'

    # RT-C4 budget/readiness
    rt4=run_red_team_round(round_id='RT-C4', fixtures=[{'fixture_id':'bud-1','exploit':True}])
    assert rt4['status']=='fail'
    # FX-C4
    slo=build_slo_roadmap_error_budget_posture(remaining=0.2)
    cap=build_cap_roadmap_capacity_budget_posture(utilization=0.7)
    qos=build_qos_roadmap_queue_pressure_forecast(queue_depth=8, throughput=4)
    assert slo['status']=='pass' and cap['status']=='pass' and qos['status'] in {'pass','warn'}
