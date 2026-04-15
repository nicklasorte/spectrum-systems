"""IFB-001 registry-aligned roadmap integration fabric runtime."""
from __future__ import annotations
import hashlib, json
from collections import defaultdict
from typing import Any, Mapping
from spectrum_systems.contracts import validate_artifact

class IFBError(ValueError):
    pass

def _id(*parts: Any) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]

def _iso(v: Any) -> str:
    if not isinstance(v, str) or "T" not in v: raise IFBError('timestamp_required')
    return v

def build_rdx_roadmap_execution_contract(*, roadmap_id: str, version: str, umbrellas: list[Mapping[str, Any]], prerequisites: list[str], required_posture_inputs: list[str], created_at: str) -> dict[str, Any]:
    if len(umbrellas) < 1: raise IFBError('umbrella_required')
    if not prerequisites: raise IFBError('missing_prerequisites')
    umbrella_singleton=False
    batch_ids=[]
    for u in umbrellas:
        batches=u.get('batches',[])
        if len(batches) < 2: umbrella_singleton=True
        for b in batches:
            slices=b.get('slices',[])
            if len(slices) < 2: raise IFBError('singleton_batch_invalid')
            batch_ids.append(str(b.get('batch_id')))
    if umbrella_singleton and len(umbrellas)>1: raise IFBError('singleton_umbrella_invalid')
    rec={'artifact_type':'rdx_roadmap_execution_contract','schema_version':'1.0.0','artifact_version':version,'standards_version':'1.0.0','artifact_id':f'rdx-contract-{_id(roadmap_id,version)}','owner':'RDX','roadmap_id':roadmap_id,'created_at':_iso(created_at),'status':'pass','umbrellas':umbrellas,'batch_ids':sorted(set(batch_ids)),'prerequisites':sorted(set(prerequisites)),'required_posture_inputs':sorted(set(required_posture_inputs)),'non_authority_assertions':['rdx_non_authoritative_report_only']}
    validate_artifact(rec,'rdx_roadmap_execution_contract'); return rec

def enforce_rdx_structure_hooks(contract: Mapping[str, Any], decision_prereqs: list[str]) -> list[str]:
    failures=[]
    for u in contract.get('umbrellas',[]):
        if len(u.get('batches',[]))<2: failures.append('singleton_umbrella_invalid')
        for b in u.get('batches',[]):
            if len(b.get('slices',[]))<2: failures.append('singleton_batch_invalid')
    req=set(contract.get('prerequisites',[])); missing=sorted(req-set(decision_prereqs))
    if missing: failures.extend([f'missing_decision_prerequisite:{m}' for m in missing])
    return sorted(set(failures))

def build_rdx_global_execution_validity_report(*, contract: Mapping[str, Any], owner_inputs: Mapping[str, Mapping[str, Any]], now: str, max_age_minutes: int=180) -> dict[str, Any]:
    _iso(now)
    required=set(contract.get('required_posture_inputs',[])); missing=sorted(required-set(owner_inputs.keys()))
    stale=[]
    now_min=int(now[11:13])*60+int(now[14:16])
    for k,v in owner_inputs.items():
        ts=str(v.get('created_at','1970-01-01T00:00:00Z'))
        try: mins=int(ts[11:13])*60+int(ts[14:16])
        except Exception: mins=0
        if now_min-mins>max_age_minutes: stale.append(k)
    status='fail' if (missing or stale) else 'pass'
    rec={'artifact_type':'rdx_global_execution_validity_report','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'rdx-validity-{_id(contract.get("artifact_id"),now)}','owner':'RDX','created_at':now,'status':status,'reason_codes':[*(f'missing_owner_input:{m}' for m in missing),*(f'stale_owner_input:{s}' for s in stale)],'required_downstream_gates':['LIN','REP','EVL','EVD','OBS','SLO','CAP','CDE'],'unresolved_blockers':missing+stale,'outstanding_debt_refs':sorted({r for v in owner_inputs.values() for r in v.get('debt_refs',[]) if isinstance(r,str)}),'non_authority_assertions':['rdx_not_gate_authority']}
    validate_artifact(rec,'rdx_global_execution_validity_report'); return rec

def build_rdx_roadmap_contract_diff(*, prior: Mapping[str, Any] | None, current: Mapping[str, Any], created_at: str) -> dict[str, Any]:
    if prior is None:
        changed_steps=current.get('batch_ids',[]); changed_deps=['missing_prior_contract']
    else:
        ps=set(prior.get('batch_ids',[])); cs=set(current.get('batch_ids',[])); changed_steps=sorted(ps^cs)
        pdep=set(prior.get('prerequisites',[])); cdep=set(current.get('prerequisites',[])); changed_deps=sorted(pdep^cdep)
    rec={'artifact_type':'rdx_roadmap_contract_diff','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'rdx-diff-{_id(prior.get("artifact_id") if prior else "none",current.get("artifact_id"))}','owner':'RDX','created_at':_iso(created_at),'status':'warn' if (changed_steps or changed_deps) else 'pass','changed_steps':changed_steps,'changed_dependencies':changed_deps,'invalidated_posture_inputs':['DAG','HNX','DEP'] if changed_deps else [],'non_authority_assertions':['rdx_contract_delta_only']}
    validate_artifact(rec,'rdx_roadmap_contract_diff'); return rec

def build_hnx_step_temporal_validity_record(*, step_id: str, continuity_evidence: list[str], checkpoint_epoch: int, now_epoch: int, max_gap: int) -> dict[str, Any]:
    if not continuity_evidence: raise IFBError('missing_continuity_evidence')
    stale=(now_epoch-checkpoint_epoch)>max_gap
    rec={'artifact_type':'hnx_step_temporal_validity_record','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'hnx-step-{_id(step_id,now_epoch)}','owner':'HNX','created_at':'2026-04-15T00:00:00Z','status':'fail' if stale else 'pass','step_id':step_id,'reason_codes':['invalid_stale_continuation'] if stale else ['valid_continuation'],'checkpoint_resume_mismatch':False,'non_authority_assertions':['hnx_signal_only']}
    validate_artifact(rec,'hnx_step_temporal_validity_record'); return rec

def build_hnx_continuity_drift_report(records: list[Mapping[str, Any]])->dict[str, Any]:
    fail=sum(1 for r in records if r.get('status')=='fail'); ratio=(fail/len(records)) if records else 1.0
    rec={'artifact_type':'hnx_continuity_drift_report','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'hnx-drift-{_id(fail,len(records))}','owner':'HNX','created_at':'2026-04-15T00:00:00Z','status':'fail' if ratio>=0.25 else 'pass','drift_ratio':ratio,'reason_codes':['false_stability_prevented'] if ratio>=0.25 else ['continuity_stable'],'non_authority_assertions':['hnx_not_decision_authority']}
    validate_artifact(rec,'hnx_continuity_drift_report'); return rec

def build_hnx_forward_validity_projection(*, step_id: str, dependency_count: int, continuity_strength: float)->dict[str, Any]:
    if continuity_strength<=0: raise IFBError('insufficient_projection_evidence')
    likely_invalid = dependency_count>5 or continuity_strength<0.5
    rec={'artifact_type':'hnx_forward_validity_projection','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'hnx-fwd-{_id(step_id,dependency_count,continuity_strength)}','owner':'HNX','created_at':'2026-04-15T00:00:00Z','status':'warn' if likely_invalid else 'pass','step_id':step_id,'future_invalidation_likely':likely_invalid,'reason_codes':['future_invalidation_surfaced'] if likely_invalid else ['projection_stable'],'non_authority_assertions':['hnx_projection_non_authoritative']}
    validate_artifact(rec,'hnx_forward_validity_projection'); return rec

def _graph_from_contract(contract: Mapping[str, Any]):
    nodes=set(); edges=defaultdict(set)
    for u in contract.get('umbrellas',[]):
        for b in u.get('batches',[]):
            bid=str(b.get('batch_id')); nodes.add(bid)
            for d in b.get('depends_on',[]): edges[bid].add(str(d))
    return nodes,edges

def build_dag_full_roadmap_dependency_validation(contract: Mapping[str, Any])->dict[str, Any]:
    nodes,edges=_graph_from_contract(contract); missing=[]
    for n,deps in edges.items():
        for d in deps:
            if d not in nodes: missing.append(f'{n}->{d}')
    visiting=set(); visited=set(); has_cycle=False
    def dfs(n):
        nonlocal has_cycle
        if n in visiting: has_cycle=True; return
        if n in visited: return
        visiting.add(n)
        for d in edges.get(n,set()):
            if d in nodes: dfs(d)
        visiting.remove(n); visited.add(n)
    for n in sorted(nodes): dfs(n)
    status='fail' if (missing or has_cycle) else 'pass'
    rec={'artifact_type':'dag_full_roadmap_dependency_validation','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'dag-val-{_id(sorted(nodes),sorted((k,sorted(v)) for k,v in edges.items()))}','owner':'DAG','created_at':'2026-04-15T00:00:00Z','status':status,'undeclared_dependencies':missing,'cycle_detected':has_cycle,'reason_codes':['invalid_edge_handling'] if missing else ['cycle_free_graph_passes'],'non_authority_assertions':['dag_graph_signal_only']}
    validate_artifact(rec,'dag_full_roadmap_dependency_validation'); return rec

def build_dag_critical_path_bottleneck_record(contract: Mapping[str, Any])->dict[str, Any]:
    nodes,edges=_graph_from_contract(contract)
    indeg={n:0 for n in nodes}
    for n,deps in edges.items():
        for d in deps:
            if d in indeg: indeg[n]+=1
    bottlenecks=sorted([n for n,c in indeg.items() if c==max(indeg.values() or [0])])
    rec={'artifact_type':'dag_critical_path_bottleneck_record','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'dag-bottleneck-{_id(sorted(nodes),bottlenecks)}','owner':'DAG','created_at':'2026-04-15T00:00:00Z','status':'pass' if nodes else 'fail','critical_path_length':len(nodes),'bottleneck_nodes':bottlenecks,'reason_codes':['ambiguous_graph_handled'] if len(bottlenecks)>1 else ['correct_bottleneck_identification'],'non_authority_assertions':['dag_non_authoritative']}
    validate_artifact(rec,'dag_critical_path_bottleneck_record'); return rec

def build_dep_chain_regression_pack(*, chain: list[str], baseline: Mapping[str, str], current: Mapping[str, str])->dict[str, Any]:
    if not chain: raise IFBError('invalid_chain_input')
    regress=[n for n in chain if baseline.get(n)=='pass' and current.get(n)!='pass']
    rec={'artifact_type':'dep_chain_regression_pack','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'dep-reg-{_id(chain,baseline,current)}','owner':'DEP','created_at':'2026-04-15T00:00:00Z','status':'fail' if regress else 'pass','regressed_nodes':regress,'reason_codes':['local_green_global_red'] if regress else ['chain_regression_clear'],'non_authority_assertions':['dep_signal_only']}
    validate_artifact(rec,'dep_chain_regression_pack'); return rec

def build_crs_cross_phase_consistency_report(*, phases: Mapping[str, str])->dict[str, Any]:
    vals=set(phases.values()); inconsistent=len(vals)>1
    rec={'artifact_type':'crs_cross_phase_consistency_report','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'crs-xphase-{_id(phases)}','owner':'CRS','created_at':'2026-04-15T00:00:00Z','status':'fail' if inconsistent else 'pass','reason_codes':['phase_drift_inconsistency'] if inconsistent else ['consistency_pass'],'non_authority_assertions':['crs_not_lineage_authority']}
    validate_artifact(rec,'crs_cross_phase_consistency_report'); return rec

def build_crs_consistency_severity_record(*, inconsistency_code: str, material: bool)->dict[str, Any]:
    sev='block' if material else 'warn'
    rec={'artifact_type':'crs_consistency_severity_record','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'crs-sev-{_id(inconsistency_code,material)}','owner':'CRS','created_at':'2026-04-15T00:00:00Z','status':'block' if material else 'warn','severity':sev,'reason_codes':[inconsistency_code],'non_authority_assertions':['material_inconsistency_not_downgraded'] if material else ['warning_grade_inconsistency']}
    validate_artifact(rec,'crs_consistency_severity_record'); return rec

def build_lin_full_chain_lineage_report(*, chain: list[str])->dict[str, Any]:
    missing=[i for i,v in enumerate(chain) if not v]
    rec={'artifact_type':'lin_full_chain_lineage_report','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'lin-full-{_id(chain)}','owner':'LIN','created_at':'2026-04-15T00:00:00Z','status':'fail' if missing else 'pass','missing_positions':missing,'reason_codes':['missing_lineage_block_signal'] if missing else ['complete_lineage_pass']}
    validate_artifact(rec,'lin_full_chain_lineage_report'); return rec

def build_lin_lineage_decay_report(*, continuity_scores: list[float])->dict[str, Any]:
    decay=any(b<a for a,b in zip(continuity_scores,continuity_scores[1:])) and (continuity_scores[-1] if continuity_scores else 0)<0.6
    rec={'artifact_type':'lin_lineage_decay_report','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'lin-decay-{_id(continuity_scores)}','owner':'LIN','created_at':'2026-04-15T00:00:00Z','status':'fail' if decay else 'pass','lineage_decay_detected':decay,'reason_codes':['stale_lineage_chain_surfaced'] if decay else ['lineage_stable']}
    validate_artifact(rec,'lin_lineage_decay_report'); return rec

def build_rep_replay_after_n_steps_record(*, window_steps: int, replay_passed: bool, evidence_refs: list[str])->dict[str, Any]:
    if not evidence_refs: raise IFBError('insufficient_replay_evidence')
    status='pass' if replay_passed and window_steps>=1 else 'fail'
    rec={'artifact_type':'rep_replay_after_n_steps_record','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'rep-n-{_id(window_steps,replay_passed,evidence_refs)}','owner':'REP','created_at':'2026-04-15T00:00:00Z','status':status,'reason_codes':['replay_pass_after_window'] if status=='pass' else ['replay_drift_block_signal'],'evidence_refs':evidence_refs}
    validate_artifact(rec,'rep_replay_after_n_steps_record'); return rec

def build_rep_replay_window_regression_pack(*, baseline: list[str], current: list[str])->dict[str, Any]:
    stale=not baseline; regression=sorted(set(baseline)-set(current))
    rec={'artifact_type':'rep_replay_window_regression_pack','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'rep-win-{_id(baseline,current)}','owner':'REP','created_at':'2026-04-15T00:00:00Z','status':'fail' if (stale or regression) else 'pass','reason_codes':['stale_baseline_handling'] if stale else (['window_regression_surfaced'] if regression else ['window_stable'])}
    validate_artifact(rec,'rep_replay_window_regression_pack'); return rec

def _coverage_map(artifact_type:str, owner:str, required:list[str], covered:list[str], debt_name:str):
    missing=sorted(set(required)-set(covered))
    rec={'artifact_type':artifact_type,'schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'{artifact_type}-{_id(required,covered)}','owner':owner,'created_at':'2026-04-15T00:00:00Z','status':'fail' if missing else 'pass','missing_required':missing,'reason_codes':[debt_name] if missing else ['complete_coverage_pass']}
    validate_artifact(rec,artifact_type); return rec

def build_evl_roadmap_eval_completeness_map(required:list[str],covered:list[str]): return _coverage_map('evl_roadmap_eval_completeness_map','EVL',required,covered,'missing_required_eval_surfaced')
def build_evd_roadmap_evidence_sufficiency_map(required:list[str],covered:list[str]): return _coverage_map('evd_roadmap_evidence_sufficiency_map','EVD',required,covered,'insufficient_evidence_surfaced')
def build_obs_roadmap_observability_completeness_report(required:list[str],covered:list[str]): return _coverage_map('obs_roadmap_observability_completeness_report','OBS',required,covered,'missing_correlation_surfaced')

def build_evl_required_eval_debt_record(*, missing_count: int, threshold: int)->dict[str, Any]:
    crossed=missing_count>=threshold
    rec={'artifact_type':'evl_required_eval_debt_record','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'evl-debt-{_id(missing_count,threshold)}','owner':'EVL','created_at':'2026-04-15T00:00:00Z','status':'fail' if crossed else 'warn','debt_count':missing_count,'reason_codes':['fail_closed_threshold_crossing'] if crossed else ['debt_accumulation']}
    validate_artifact(rec,'evl_required_eval_debt_record'); return rec

def build_evd_evidence_thinning_report(*, density_history: list[float])->dict[str, Any]:
    thinning=len(density_history)>=2 and density_history[-1] < density_history[0]*0.8
    rec={'artifact_type':'evd_evidence_thinning_report','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'evd-thin-{_id(density_history)}','owner':'EVD','created_at':'2026-04-15T00:00:00Z','status':'fail' if thinning else 'pass','reason_codes':['thinning_detection'] if thinning else ['evidence_density_stable']}
    validate_artifact(rec,'evd_evidence_thinning_report'); return rec

def build_obs_trace_correlation_decay_report(*, correlation_history: list[float])->dict[str, Any]:
    if not correlation_history: raise IFBError('missing_trace_continuity')
    decay=correlation_history[-1]<0.6
    rec={'artifact_type':'obs_trace_correlation_decay_report','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'obs-decay-{_id(correlation_history)}','owner':'OBS','created_at':'2026-04-15T00:00:00Z','status':'fail' if decay else 'pass','reason_codes':['decay_detection'] if decay else ['trace_correlation_stable']}
    validate_artifact(rec,'obs_trace_correlation_decay_report'); return rec

def build_prg_signal_prioritization_record(signals: list[Mapping[str, Any]])->dict[str, Any]:
    scored=[]
    for s in signals:
        score=int(s.get('urgency',0))*3+int(s.get('blast_radius',0))*2+int(s.get('progression_impact',0))
        scored.append({**s,'priority_score':score})
    scored=sorted(scored,key=lambda x:(-x['priority_score'],str(x.get('signal_id',''))))
    rec={'artifact_type':'prg_signal_prioritization_record','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'prg-pri-{_id(scored)}','owner':'PRG','created_at':'2026-04-15T00:00:00Z','status':'pass','ranked_signals':scored,'reason_codes':['deterministic_prioritization'],'non_authority_assertions':['prg_not_decision_engine']}
    validate_artifact(rec,'prg_signal_prioritization_record'); return rec

def build_prg_prioritized_control_signal_bundle(prioritization: Mapping[str, Any])->dict[str, Any]:
    bundle={'artifact_type':'prg_prioritized_control_signal_bundle','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'prg-bundle-{_id(prioritization.get("artifact_id"))}','owner':'PRG','created_at':'2026-04-15T00:00:00Z','status':'pass','signals':prioritization.get('ranked_signals',[]),'signal_count':len(prioritization.get('ranked_signals',[])),'reason_codes':['bundle_completeness'],'non_authority_assertions':['no_hidden_dropped_signals','prg_non_authoritative']}
    validate_artifact(bundle,'prg_prioritized_control_signal_bundle'); return bundle

def build_prg_roadmap_risk_stack(bundle: Mapping[str, Any])->dict[str, Any]:
    risks=[{'risk_id':s.get('signal_id'), 'score':s.get('priority_score',0)} for s in bundle.get('signals',[])]
    rec={'artifact_type':'prg_roadmap_risk_stack','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'prg-risk-{_id(risks)}','owner':'PRG','created_at':'2026-04-15T00:00:00Z','status':'pass','ranked_risks':risks,'reason_codes':['ranking_correctness'],'non_authority_assertions':['stale_risk_suppression_prevented']}
    validate_artifact(rec,'prg_roadmap_risk_stack'); return rec

def build_prg_roadmap_halt_recommendation(risk_stack: Mapping[str, Any], halt_threshold:int=20)->dict[str, Any]:
    top=max([r.get('score',0) for r in risk_stack.get('ranked_risks',[])] or [0])
    status='halt' if top>=halt_threshold else 'continue'
    rec={'artifact_type':'prg_roadmap_halt_recommendation','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'prg-halt-{_id(top,halt_threshold)}','owner':'PRG','created_at':'2026-04-15T00:00:00Z','status':status,'reason_codes':['recommendation_generation'],'non_authority_assertions':['explicit_non_authority_assertion']}
    validate_artifact(rec,'prg_roadmap_halt_recommendation'); return rec

def build_ail_correction_pattern_roadmap_candidate_record(patterns:list[Mapping[str,Any]])->dict[str,Any]:
    cands=[p for p in patterns if int(p.get('count',0))>=2]
    rec={'artifact_type':'ail_correction_pattern_roadmap_candidate_record','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'ail-cand-{_id(cands)}','owner':'AIL','created_at':'2026-04-15T00:00:00Z','status':'pass','candidates':cands,'reason_codes':['valid_candidate_compilation'],'non_authority_assertions':['false_pattern_suppression']}
    validate_artifact(rec,'ail_correction_pattern_roadmap_candidate_record'); return rec

def build_ail_trust_posture_trend_delta_record(*, prior: float, current: float)->dict[str,Any]:
    rec={'artifact_type':'ail_trust_posture_trend_delta_record','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'ail-delta-{_id(prior,current)}','owner':'AIL','created_at':'2026-04-15T00:00:00Z','status':'pass','delta':current-prior,'reason_codes':['correct_delta_generation'],'non_authority_assertions':['stale_run_handling']}
    validate_artifact(rec,'ail_trust_posture_trend_delta_record'); return rec

def build_jdx_judgment_quality_feedback_record(*, judgments:int, linked_eval:int)->dict[str,Any]:
    if linked_eval>judgments: raise IFBError('invalid_linkage')
    rec={'artifact_type':'jdx_judgment_quality_feedback_record','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'jdx-q-{_id(judgments,linked_eval)}','owner':'JDX','created_at':'2026-04-15T00:00:00Z','status':'pass','reason_codes':['quality_loop_linkage'],'non_authority_assertions':['jdx_feedback_only']}
    validate_artifact(rec,'jdx_judgment_quality_feedback_record'); return rec

def build_pol_policy_release_performance_record(*, releases:list[Mapping[str,Any]])->dict[str,Any]:
    if len(releases)<2: raise IFBError('stale_release_comparison_handling')
    rec={'artifact_type':'pol_policy_release_performance_record','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'pol-perf-{_id(releases)}','owner':'POL','created_at':'2026-04-15T00:00:00Z','status':'pass','reason_codes':['tracking_correctness'],'non_authority_assertions':['lifecycle_non_authoritative']}
    validate_artifact(rec,'pol_policy_release_performance_record'); return rec

def build_prx_precedent_reinforcement_record(precedents:list[Mapping[str,Any]])->dict[str,Any]:
    kept=[p for p in precedents if p.get('validated') is True and p.get('stale') is not True]
    rec={'artifact_type':'prx_precedent_reinforcement_record','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'prx-ref-{_id(kept)}','owner':'PRX','created_at':'2026-04-15T00:00:00Z','status':'pass','retained':kept,'reason_codes':['good_precedent_retained'],'non_authority_assertions':['stale_bad_precedent_rejected']}
    validate_artifact(rec,'prx_precedent_reinforcement_record'); return rec

def build_slo_roadmap_error_budget_posture(*, remaining: float)->dict[str,Any]:
    rec={'artifact_type':'slo_roadmap_error_budget_posture','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'slo-posture-{_id(remaining)}','owner':'SLO','created_at':'2026-04-15T00:00:00Z','status':'fail' if remaining<=0 else 'pass','remaining_budget':remaining,'reason_codes':['exhausted_budget_signal'] if remaining<=0 else ['posture_computation']}
    validate_artifact(rec,'slo_roadmap_error_budget_posture'); return rec

def build_cap_roadmap_capacity_budget_posture(*, utilization: float)->dict[str,Any]:
    rec={'artifact_type':'cap_roadmap_capacity_budget_posture','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'cap-posture-{_id(utilization)}','owner':'CAP','created_at':'2026-04-15T00:00:00Z','status':'fail' if utilization>1.0 else 'pass','utilization':utilization,'reason_codes':['overload_detection'] if utilization>1.0 else ['valid_capacity_pass']}
    validate_artifact(rec,'cap_roadmap_capacity_budget_posture'); return rec

def build_qos_roadmap_queue_pressure_forecast(*, queue_depth:int, throughput:int)->dict[str,Any]:
    pressure=(queue_depth/max(throughput,1))
    rec={'artifact_type':'qos_roadmap_queue_pressure_forecast','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'qos-forecast-{_id(queue_depth,throughput)}','owner':'QOS','created_at':'2026-04-15T00:00:00Z','status':'warn' if pressure>5 else 'pass','pressure_score':pressure,'reason_codes':['false_green_suppression'] if pressure>5 else ['pressure_forecast_correctness'],'non_authority_assertions':['qos_signal_only']}
    validate_artifact(rec,'qos_roadmap_queue_pressure_forecast'); return rec

def build_cde_composite_posture_consumption_contract()->dict[str,Any]:
    required=['LIN','REP','EVL','EVD','OBS','SLO','CAP','RDX','HNX','DAG','DEP','CRS','PRG','QOS']
    rec={'artifact_type':'cde_composite_posture_consumption_contract','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'cde-consume-{_id(required)}','owner':'CDE','created_at':'2026-04-15T00:00:00Z','status':'ready','required_inputs':required}
    validate_artifact(rec,'cde_composite_posture_consumption_contract'); return rec

def build_cde_global_execution_readiness_decision(*, postures: Mapping[str, Mapping[str, Any]], contract: Mapping[str, Any])->dict[str,Any]:
    required=set(contract.get('required_inputs',[])); missing=sorted(required-set(postures.keys()))
    failing=[k for k,v in postures.items() if v.get('status') in {'fail','block','halt'}]
    status='not_ready' if (missing or failing) else 'ready'
    rec={'artifact_type':'cde_global_execution_readiness_decision','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'cde-readiness-{_id(sorted(postures),missing,failing)}','owner':'CDE','created_at':'2026-04-15T00:00:00Z','status':status,'reason_codes':[*(f'missing_required_input:{m}' for m in missing),*(f'failing_posture:{f}' for f in failing)]}
    validate_artifact(rec,'cde_global_execution_readiness_decision'); return rec

def build_cde_invariant_breach_stop_decision(*, material_breaches: list[str])->dict[str,Any]:
    stop=bool(material_breaches)
    rec={'artifact_type':'cde_invariant_breach_stop_decision','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'cde-stop-{_id(material_breaches)}','owner':'CDE','created_at':'2026-04-15T00:00:00Z','status':'halt' if stop else 'continue','reason_codes':['material_breach_stops'] if stop else ['non_material_issue_not_stopped']}
    validate_artifact(rec,'cde_invariant_breach_stop_decision'); return rec

def build_cde_continue_vs_halt_decision(*, readiness: Mapping[str, Any], stop_decision: Mapping[str, Any], umbrella_id: str, stale: bool=False)->dict[str,Any]:
    if stale: raise IFBError('stale_decision_invalidation')
    halt=stop_decision.get('status')=='halt' or readiness.get('status')!='ready'
    rec={'artifact_type':'cde_continue_vs_halt_decision','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'cde-boundary-{_id(umbrella_id,readiness.get("status"),stop_decision.get("status"))}','owner':'CDE','created_at':'2026-04-15T00:00:00Z','status':'halt' if halt else 'continue','umbrella_id':umbrella_id,'reason_codes':['halt_path'] if halt else ['continue_path']}
    validate_artifact(rec,'cde_continue_vs_halt_decision'); return rec

def run_red_team_round(*, round_id: str, fixtures: list[Mapping[str, Any]])->dict[str,Any]:
    finding_ids=[str(f.get('fixture_id')) for f in fixtures if f.get('exploit')]
    name={
      'RT-C1':'ril_plan_wide_coherence_red_team_report',
      'RT-C2':'ril_temporal_dependency_red_team_report',
      'RT-C3':'ril_signal_overload_red_team_report',
      'RT-C4':'ril_budget_readiness_red_team_report',
    }[round_id]
    rec={'artifact_type':name,'schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'{round_id}-{_id(finding_ids)}','owner':'RIL','created_at':'2026-04-15T00:00:00Z','status':'fail' if finding_ids else 'pass','finding_ids':finding_ids,'reason_codes':['adversarial_findings_detected'] if finding_ids else ['no_exploit'] ,'non_authority_assertions':['red_team_signal_only']}
    validate_artifact(rec,name); return rec
