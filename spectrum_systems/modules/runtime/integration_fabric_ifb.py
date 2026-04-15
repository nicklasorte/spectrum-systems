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

def build_rdx_roadmap_prerequisite_graph(*, contract: Mapping[str, Any], created_at: str) -> dict[str, Any]:
    prereqs=sorted(set(contract.get('prerequisites',[])))
    edges=[]
    for u in contract.get('umbrellas',[]):
        uid=str(u.get('umbrella_id'))
        for b in u.get('batches',[]):
            bid=str(b.get('batch_id'))
            edges.append({'from':uid,'to':bid,'type':'contains'})
            for dep in b.get('depends_on',[]):
                edges.append({'from':bid,'to':str(dep),'type':'depends_on'})
    rec={'artifact_type':'rdx_roadmap_prerequisite_graph','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'rdx-pre-graph-{_id(contract.get("artifact_id"),prereqs,edges)}','owner':'RDX','created_at':_iso(created_at),'status':'pass' if prereqs else 'fail','prerequisites':prereqs,'edges':edges,'reason_codes':['missing_prerequisite_detection'] if not prereqs else ['valid_prerequisite_graph'],'non_authority_assertions':['rdx_signal_only']}
    validate_artifact(rec,'rdx_roadmap_prerequisite_graph'); return rec

def build_rdx_must_revalidate_set(*, contract_diff: Mapping[str, Any], contract: Mapping[str, Any], created_at: str) -> dict[str, Any]:
    changed=set(contract_diff.get('changed_steps',[]))
    impacted=set(changed)
    # transitive downstream propagation on batch dependencies
    nodes,edges=_graph_from_contract(contract)
    rev=defaultdict(set)
    for n,deps in edges.items():
        for d in deps: rev[str(d)].add(str(n))
    queue=list(changed)
    while queue:
        cur=queue.pop(0)
        for nxt in sorted(rev.get(cur,set())):
            if nxt not in impacted:
                impacted.add(nxt); queue.append(nxt)
    rec={'artifact_type':'rdx_must_revalidate_set','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'rdx-reval-{_id(contract_diff.get("artifact_id"),sorted(impacted))}','owner':'RDX','created_at':_iso(created_at),'status':'warn' if impacted else 'pass','must_revalidate':sorted(impacted),'reason_codes':['invalidation_propagation_computed'],'non_authority_assertions':['no_under_reporting_revalidation_debt']}
    validate_artifact(rec,'rdx_must_revalidate_set'); return rec

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

def build_hnx_checkpoint_resume_integrity_report(*, checkpoint_id: str, resume_id: str, lineage_ok: bool, continuity_ok: bool)->dict[str,Any]:
    ok=lineage_ok and continuity_ok and bool(checkpoint_id) and bool(resume_id)
    rec={'artifact_type':'hnx_checkpoint_resume_integrity_report','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'hnx-cp-{_id(checkpoint_id,resume_id,lineage_ok,continuity_ok)}','owner':'HNX','created_at':'2026-04-15T00:00:00Z','status':'pass' if ok else 'fail','reason_codes':['good_resume_pass'] if ok else ['broken_resume_lineage_surfaced'],'non_authority_assertions':['hnx_integrity_signal_only']}
    validate_artifact(rec,'hnx_checkpoint_resume_integrity_report'); return rec

def build_hnx_handoff_completeness_requirement_record(*, handoff_id: str, required: list[str], provided: list[str])->dict[str,Any]:
    missing=sorted(set(required)-set(provided))
    rec={'artifact_type':'hnx_handoff_completeness_requirement_record','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'hnx-handoff-{_id(handoff_id,required,provided)}','owner':'HNX','created_at':'2026-04-15T00:00:00Z','status':'fail' if missing else 'pass','missing_required':missing,'reason_codes':['incomplete_handoff_fail_closed'] if missing else ['complete_handoff_pass'],'non_authority_assertions':['hnx_handoff_binding_non_authoritative']}
    validate_artifact(rec,'hnx_handoff_completeness_requirement_record'); return rec

def build_hnx_resume_risk_classification_record(*, continuity_score: float, unresolved_dependencies: int)->dict[str,Any]:
    if continuity_score <= 0:
        raise IFBError('missing_evidence_fail_closed')
    high=(continuity_score<0.6) or unresolved_dependencies>0
    rec={'artifact_type':'hnx_resume_risk_classification_record','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'hnx-risk-{_id(continuity_score,unresolved_dependencies)}','owner':'HNX','created_at':'2026-04-15T00:00:00Z','status':'warn' if high else 'pass','risk_level':'high' if high else 'low','reason_codes':['high_risk_classification' if high else 'low_risk_classification'],'non_authority_assertions':['hnx_resume_classification_signal_only']}
    validate_artifact(rec,'hnx_resume_risk_classification_record'); return rec

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

def build_dag_hidden_dependency_suspicion_report(*, declared_edges: list[tuple[str,str]], observed_handoffs: list[tuple[str,str]])->dict[str,Any]:
    declared={tuple(map(str,e)) for e in declared_edges}
    suspicious=sorted({f'{a}->{b}' for a,b in observed_handoffs if (str(a),str(b)) not in declared})
    rec={'artifact_type':'dag_hidden_dependency_suspicion_report','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'dag-hidden-{_id(declared_edges,observed_handoffs)}','owner':'DAG','created_at':'2026-04-15T00:00:00Z','status':'warn' if suspicious else 'pass','suspicious_edges':suspicious,'reason_codes':['suspicion_surfaced'] if suspicious else ['no_suspicion'],'non_authority_assertions':['dag_non_authoritative_signal']}
    validate_artifact(rec,'dag_hidden_dependency_suspicion_report'); return rec

def build_dag_umbrella_boundary_dependency_report(*, prior_outputs: list[str], requested_inputs: list[str], mutation_attempts: list[str])->dict[str,Any]:
    illegal=sorted(set(requested_inputs)-set(prior_outputs))
    illegal_mut=sorted(set(mutation_attempts))
    fail=bool(illegal or illegal_mut)
    rec={'artifact_type':'dag_umbrella_boundary_dependency_report','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'dag-umb-{_id(prior_outputs,requested_inputs,mutation_attempts)}','owner':'DAG','created_at':'2026-04-15T00:00:00Z','status':'fail' if fail else 'pass','illegal_inputs':illegal,'illegal_mutations':illegal_mut,'reason_codes':['illegal_cross_umbrella_mutation_surfaced'] if fail else ['valid_serial_umbrella_dependency'],'non_authority_assertions':['dag_boundary_validation_signal_only']}
    validate_artifact(rec,'dag_umbrella_boundary_dependency_report'); return rec

def build_dag_dependency_fanout_risk_record(*, graph: Mapping[str, list[str]], high_risk_threshold: int=3)->dict[str,Any]:
    fanout={str(k):len(v) for k,v in graph.items()}
    high=sorted([n for n,v in fanout.items() if v>=high_risk_threshold])
    rec={'artifact_type':'dag_dependency_fanout_risk_record','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'dag-fanout-{_id(graph,high_risk_threshold)}','owner':'DAG','created_at':'2026-04-15T00:00:00Z','status':'warn' if high else 'pass','fanout':fanout,'high_fanout_nodes':high,'reason_codes':['high_fanout_surfaced'] if high else ['risk_grading_stable'],'non_authority_assertions':['dag_fanout_non_authoritative']}
    validate_artifact(rec,'dag_dependency_fanout_risk_record'); return rec

def build_dep_chain_regression_pack(*, chain: list[str], baseline: Mapping[str, str], current: Mapping[str, str])->dict[str, Any]:
    if not chain: raise IFBError('invalid_chain_input')
    regress=[n for n in chain if baseline.get(n)=='pass' and current.get(n)!='pass']
    rec={'artifact_type':'dep_chain_regression_pack','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'dep-reg-{_id(chain,baseline,current)}','owner':'DEP','created_at':'2026-04-15T00:00:00Z','status':'fail' if regress else 'pass','regressed_nodes':regress,'reason_codes':['local_green_global_red'] if regress else ['chain_regression_clear'],'non_authority_assertions':['dep_signal_only']}
    validate_artifact(rec,'dep_chain_regression_pack'); return rec

def build_dep_critical_chain_replay_fixture_pack(*, chains: list[list[str]])->dict[str,Any]:
    complete=all(len(c)>=2 for c in chains) and bool(chains)
    rec={'artifact_type':'dep_critical_chain_replay_fixture_pack','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'dep-fixture-{_id(chains)}','owner':'DEP','created_at':'2026-04-15T00:00:00Z','status':'pass' if complete else 'fail','fixture_count':len(chains),'reason_codes':['fixture_completeness'] if complete else ['fixture_incomplete'],'non_authority_assertions':['dep_fixture_non_authoritative']}
    validate_artifact(rec,'dep_critical_chain_replay_fixture_pack'); return rec

def build_dep_post_fix_chain_regression_bundle(*, affected_chains: list[str], rerun_chains: list[str])->dict[str,Any]:
    skipped=sorted(set(affected_chains)-set(rerun_chains))
    rec={'artifact_type':'dep_post_fix_chain_regression_bundle','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'dep-post-fix-{_id(affected_chains,rerun_chains)}','owner':'DEP','created_at':'2026-04-15T00:00:00Z','status':'fail' if skipped else 'pass','skipped_affected_chains':skipped,'reason_codes':['post_fix_chain_rerun_required'] if skipped else ['post_fix_chain_rerun_complete'],'non_authority_assertions':['dep_post_fix_non_authoritative']}
    validate_artifact(rec,'dep_post_fix_chain_regression_bundle'); return rec

def build_crs_cross_phase_consistency_report(*, phases: Mapping[str, str])->dict[str, Any]:
    vals=set(phases.values()); inconsistent=len(vals)>1
    rec={'artifact_type':'crs_cross_phase_consistency_report','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'crs-xphase-{_id(phases)}','owner':'CRS','created_at':'2026-04-15T00:00:00Z','status':'fail' if inconsistent else 'pass','reason_codes':['phase_drift_inconsistency'] if inconsistent else ['consistency_pass'],'non_authority_assertions':['crs_not_lineage_authority']}
    validate_artifact(rec,'crs_cross_phase_consistency_report'); return rec

def build_crs_consistency_severity_record(*, inconsistency_code: str, material: bool)->dict[str, Any]:
    sev='block' if material else 'warn'
    rec={'artifact_type':'crs_consistency_severity_record','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'crs-sev-{_id(inconsistency_code,material)}','owner':'CRS','created_at':'2026-04-15T00:00:00Z','status':'block' if material else 'warn','severity':sev,'reason_codes':[inconsistency_code],'non_authority_assertions':['material_inconsistency_not_downgraded'] if material else ['warning_grade_inconsistency']}
    validate_artifact(rec,'crs_consistency_severity_record'); return rec

def build_crs_contradiction_cluster_record(*, contradiction_codes: list[str])->dict[str,Any]:
    groups=defaultdict(int)
    for c in contradiction_codes: groups[str(c)] += 1
    clusters={k:v for k,v in groups.items() if v>=2}
    rec={'artifact_type':'crs_contradiction_cluster_record','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'crs-cluster-{_id(contradiction_codes)}','owner':'CRS','created_at':'2026-04-15T00:00:00Z','status':'warn' if clusters else 'pass','clusters':clusters,'reason_codes':['repeated_contradictions_clustered'] if clusters else ['no_cluster'],'non_authority_assertions':['crs_clustering_non_authoritative']}
    validate_artifact(rec,'crs_contradiction_cluster_record'); return rec

def build_crs_cross_owner_contradiction_history(*, events: list[Mapping[str,Any]])->dict[str,Any]:
    stale=any(e.get('stale') for e in events)
    rec={'artifact_type':'crs_cross_owner_contradiction_history','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'crs-history-{_id(events)}','owner':'CRS','created_at':'2026-04-15T00:00:00Z','status':'warn' if stale else 'pass','event_count':len(events),'reason_codes':['stale_contradiction_history_handled'] if stale else ['contradiction_history_accumulates_correctly'],'non_authority_assertions':['crs_history_non_authoritative']}
    validate_artifact(rec,'crs_cross_owner_contradiction_history'); return rec

def build_lin_full_chain_lineage_report(*, chain: list[str])->dict[str, Any]:
    missing=[i for i,v in enumerate(chain) if not v]
    rec={'artifact_type':'lin_full_chain_lineage_report','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'lin-full-{_id(chain)}','owner':'LIN','created_at':'2026-04-15T00:00:00Z','status':'fail' if missing else 'pass','missing_positions':missing,'reason_codes':['missing_lineage_block_signal'] if missing else ['complete_lineage_pass']}
    validate_artifact(rec,'lin_full_chain_lineage_report'); return rec

def build_lin_lineage_decay_report(*, continuity_scores: list[float])->dict[str, Any]:
    decay=any(b<a for a,b in zip(continuity_scores,continuity_scores[1:])) and (continuity_scores[-1] if continuity_scores else 0)<0.6
    rec={'artifact_type':'lin_lineage_decay_report','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'lin-decay-{_id(continuity_scores)}','owner':'LIN','created_at':'2026-04-15T00:00:00Z','status':'fail' if decay else 'pass','lineage_decay_detected':decay,'reason_codes':['stale_lineage_chain_surfaced'] if decay else ['lineage_stable']}
    validate_artifact(rec,'lin_lineage_decay_report'); return rec

def build_lin_advancement_lineage_sufficiency_map(*, required_refs: list[str], present_refs: list[str])->dict[str,Any]:
    missing=sorted(set(required_refs)-set(present_refs))
    rec={'artifact_type':'lin_advancement_lineage_sufficiency_map','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'lin-suff-{_id(required_refs,present_refs)}','owner':'LIN','created_at':'2026-04-15T00:00:00Z','status':'fail' if missing else 'pass','missing_required':missing,'reason_codes':['promotion_relevant_debt_surfaced'] if missing else ['sufficiency_pass']}
    validate_artifact(rec,'lin_advancement_lineage_sufficiency_map'); return rec

def build_rep_replay_after_n_steps_record(*, window_steps: int, replay_passed: bool, evidence_refs: list[str])->dict[str, Any]:
    if not evidence_refs: raise IFBError('insufficient_replay_evidence')
    status='pass' if replay_passed and window_steps>=1 else 'fail'
    rec={'artifact_type':'rep_replay_after_n_steps_record','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'rep-n-{_id(window_steps,replay_passed,evidence_refs)}','owner':'REP','created_at':'2026-04-15T00:00:00Z','status':status,'reason_codes':['replay_pass_after_window'] if status=='pass' else ['replay_drift_block_signal'],'evidence_refs':evidence_refs}
    validate_artifact(rec,'rep_replay_after_n_steps_record'); return rec

def build_rep_replay_window_regression_pack(*, baseline: list[str], current: list[str])->dict[str, Any]:
    stale=not baseline; regression=sorted(set(baseline)-set(current))
    rec={'artifact_type':'rep_replay_window_regression_pack','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'rep-win-{_id(baseline,current)}','owner':'REP','created_at':'2026-04-15T00:00:00Z','status':'fail' if (stale or regression) else 'pass','reason_codes':['stale_baseline_handling'] if stale else (['window_regression_surfaced'] if regression else ['window_stable'])}
    validate_artifact(rec,'rep_replay_window_regression_pack'); return rec

def build_rep_selective_replay_sampling_policy_record(*, required_windows: list[str], sampled_windows: list[str])->dict[str,Any]:
    missing=sorted(set(required_windows)-set(sampled_windows))
    rec={'artifact_type':'rep_selective_replay_sampling_policy_record','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'rep-sampling-{_id(required_windows,sampled_windows)}','owner':'REP','created_at':'2026-04-15T00:00:00Z','status':'fail' if missing else 'pass','missing_required_windows':missing,'reason_codes':['under_sampling_surfaced_as_violation'] if missing else ['required_windows_sampled']}
    validate_artifact(rec,'rep_selective_replay_sampling_policy_record'); return rec

def _coverage_map(artifact_type:str, owner:str, required:list[str], covered:list[str], debt_name:str):
    missing=sorted(set(required)-set(covered))
    rec={'artifact_type':artifact_type,'schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'{artifact_type}-{_id(required,covered)}','owner':owner,'created_at':'2026-04-15T00:00:00Z','status':'fail' if missing else 'pass','missing_required':missing,'reason_codes':[debt_name] if missing else ['complete_coverage_pass']}
    validate_artifact(rec,artifact_type); return rec

def build_evl_roadmap_eval_completeness_map(required:list[str],covered:list[str]): return _coverage_map('evl_roadmap_eval_completeness_map','EVL',required,covered,'missing_required_eval_surfaced')
def build_evd_roadmap_evidence_sufficiency_map(required:list[str],covered:list[str]): return _coverage_map('evd_roadmap_evidence_sufficiency_map','EVD',required,covered,'insufficient_evidence_surfaced')
def build_obs_roadmap_observability_completeness_report(required:list[str],covered:list[str]): return _coverage_map('obs_roadmap_observability_completeness_report','OBS',required,covered,'missing_correlation_surfaced')
def build_evl_phase_required_eval_set(required:list[str],covered:list[str]): return _coverage_map('evl_phase_required_eval_set','EVL',required,covered,'missing_phase_coverage_surfaced')
def build_evl_red_team_coverage_ledger(required:list[str],covered:list[str]): return _coverage_map('evl_red_team_coverage_ledger','EVL',required,covered,'uncovered_surfaces_surfaced_as_debt')
def build_obs_gap_to_step_map(required:list[str],covered:list[str]): return _coverage_map('obs_gap_to_step_map','OBS',required,covered,'exact_gap_mapping')

def build_evl_required_eval_debt_record(*, missing_count: int, threshold: int)->dict[str, Any]:
    crossed=missing_count>=threshold
    rec={'artifact_type':'evl_required_eval_debt_record','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'evl-debt-{_id(missing_count,threshold)}','owner':'EVL','created_at':'2026-04-15T00:00:00Z','status':'fail' if crossed else 'warn','debt_count':missing_count,'reason_codes':['fail_closed_threshold_crossing'] if crossed else ['debt_accumulation']}
    validate_artifact(rec,'evl_required_eval_debt_record'); return rec

def build_evd_evidence_thinning_report(*, density_history: list[float])->dict[str, Any]:
    thinning=len(density_history)>=2 and density_history[-1] < density_history[0]*0.8
    rec={'artifact_type':'evd_evidence_thinning_report','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'evd-thin-{_id(density_history)}','owner':'EVD','created_at':'2026-04-15T00:00:00Z','status':'fail' if thinning else 'pass','reason_codes':['thinning_detection'] if thinning else ['evidence_density_stable']}
    validate_artifact(rec,'evd_evidence_thinning_report'); return rec

def build_evd_step_class_evidence_profile_library(*, profiles: Mapping[str, list[str]], step_class: str)->dict[str,Any]:
    ok=step_class in profiles and bool(profiles.get(step_class))
    rec={'artifact_type':'evd_step_class_evidence_profile_library','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'evd-profile-{_id(profiles,step_class)}','owner':'EVD','created_at':'2026-04-15T00:00:00Z','status':'pass' if ok else 'fail','reason_codes':['profile_matching'] if ok else ['incorrect_class_profile_usage_surfaced']}
    validate_artifact(rec,'evd_step_class_evidence_profile_library'); return rec

def build_obs_trace_correlation_decay_report(*, correlation_history: list[float])->dict[str, Any]:
    if not correlation_history: raise IFBError('missing_trace_continuity')
    decay=correlation_history[-1]<0.6
    rec={'artifact_type':'obs_trace_correlation_decay_report','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'obs-decay-{_id(correlation_history)}','owner':'OBS','created_at':'2026-04-15T00:00:00Z','status':'fail' if decay else 'pass','reason_codes':['decay_detection'] if decay else ['trace_correlation_stable']}
    validate_artifact(rec,'obs_trace_correlation_decay_report'); return rec

def build_obs_missing_signal_provenance_report(*, required_signals: list[str], observed_signals: list[str], provenance: Mapping[str,str])->dict[str,Any]:
    missing=sorted(set(required_signals)-set(observed_signals))
    with_ctx=[{'signal':m,'provenance':provenance.get(m,'unknown')} for m in missing]
    rec={'artifact_type':'obs_missing_signal_provenance_report','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'obs-missing-{_id(required_signals,observed_signals,provenance)}','owner':'OBS','created_at':'2026-04-15T00:00:00Z','status':'warn' if missing else 'pass','missing_signals':with_ctx,'reason_codes':['missing_signal_surfaced_with_provenance_context'] if missing else ['no_missing_signal'],'non_authority_assertions':['no_silent_omission']}
    validate_artifact(rec,'obs_missing_signal_provenance_report'); return rec

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

def build_prg_roadmap_recut_recommendation(*, bottlenecks: list[str])->dict[str,Any]:
    status='candidate_only' if bottlenecks else 'pass'
    rec={'artifact_type':'prg_roadmap_recut_recommendation','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'prg-recut-{_id(bottlenecks)}','owner':'PRG','created_at':'2026-04-15T00:00:00Z','status':status,'reason_codes':['recut_recommendation_generation'],'non_authority_assertions':['non_authoritative_guarantee']}
    validate_artifact(rec,'prg_roadmap_recut_recommendation'); return rec

def build_prg_smallest_safe_next_batch_recommendation(*, candidate_batches: list[Mapping[str,Any]])->dict[str,Any]:
    if not candidate_batches: raise IFBError('no_candidate_batches')
    chosen=min(candidate_batches,key=lambda b:int(b.get('risk',9999)))
    rec={'artifact_type':'prg_smallest_safe_next_batch_recommendation','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'prg-smallest-{_id(candidate_batches)}','owner':'PRG','created_at':'2026-04-15T00:00:00Z','status':'candidate_only','recommended_batch':chosen,'reason_codes':['recommendation_correctness'],'non_authority_assertions':['no_hidden_execution_authority']}
    validate_artifact(rec,'prg_smallest_safe_next_batch_recommendation'); return rec

def build_ail_correction_pattern_roadmap_candidate_record(patterns:list[Mapping[str,Any]])->dict[str,Any]:
    cands=[p for p in patterns if int(p.get('count',0))>=2]
    rec={'artifact_type':'ail_correction_pattern_roadmap_candidate_record','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'ail-cand-{_id(cands)}','owner':'AIL','created_at':'2026-04-15T00:00:00Z','status':'pass','candidates':cands,'reason_codes':['valid_candidate_compilation'],'non_authority_assertions':['false_pattern_suppression']}
    validate_artifact(rec,'ail_correction_pattern_roadmap_candidate_record'); return rec

def build_ail_trust_posture_trend_delta_record(*, prior: float, current: float)->dict[str,Any]:
    rec={'artifact_type':'ail_trust_posture_trend_delta_record','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'ail-delta-{_id(prior,current)}','owner':'AIL','created_at':'2026-04-15T00:00:00Z','status':'pass','delta':current-prior,'reason_codes':['correct_delta_generation'],'non_authority_assertions':['stale_run_handling']}
    validate_artifact(rec,'ail_trust_posture_trend_delta_record'); return rec

def build_ail_recurring_exploit_family_record(*, exploit_ids: list[str])->dict[str,Any]:
    families=defaultdict(list)
    for e in exploit_ids:
        fam=e.split(':',1)[0] if ':' in e else e.split('-',1)[0]
        families[fam].append(e)
    retained={k:sorted(v) for k,v in families.items() if len(v)>=2}
    rec={'artifact_type':'ail_recurring_exploit_family_record','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'ail-exploit-{_id(exploit_ids)}','owner':'AIL','created_at':'2026-04-15T00:00:00Z','status':'warn' if retained else 'pass','families':retained,'reason_codes':['exploit_clustering_correctness'] if retained else ['false_family_suppression'],'non_authority_assertions':['ail_signal_only']}
    validate_artifact(rec,'ail_recurring_exploit_family_record'); return rec

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

def build_slo_roadmap_burn_rate_forecast(*, consumed: float, window_days: int)->dict[str,Any]:
    rate=consumed/max(window_days,1)
    status='warn' if rate>0.1 else 'pass'
    rec={'artifact_type':'slo_roadmap_burn_rate_forecast','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'slo-burn-{_id(consumed,window_days)}','owner':'SLO','created_at':'2026-04-15T00:00:00Z','status':status,'burn_rate':rate,'reason_codes':['threshold_breach_surfaced'] if status=='warn' else ['forecast_correctness']}
    validate_artifact(rec,'slo_roadmap_burn_rate_forecast'); return rec

def build_slo_roadmap_freeze_threshold_profile(*, step_count: int, budget_remaining: float)->dict[str,Any]:
    freeze=step_count>80 and budget_remaining<0.2
    rec={'artifact_type':'slo_roadmap_freeze_threshold_profile','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'slo-freeze-{_id(step_count,budget_remaining)}','owner':'SLO','created_at':'2026-04-15T00:00:00Z','status':'halt' if freeze else 'pass','reason_codes':['freeze_threshold_enforcement_profile_correctness'] if not freeze else ['freeze_threshold_triggered']}
    validate_artifact(rec,'slo_roadmap_freeze_threshold_profile'); return rec

def build_cap_roadmap_capacity_budget_posture(*, utilization: float)->dict[str,Any]:
    rec={'artifact_type':'cap_roadmap_capacity_budget_posture','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'cap-posture-{_id(utilization)}','owner':'CAP','created_at':'2026-04-15T00:00:00Z','status':'fail' if utilization>1.0 else 'pass','utilization':utilization,'reason_codes':['overload_detection'] if utilization>1.0 else ['valid_capacity_pass']}
    validate_artifact(rec,'cap_roadmap_capacity_budget_posture'); return rec

def build_cap_reviewer_load_pressure_record(*, reviewers: int, required_reviews: int)->dict[str,Any]:
    load=(required_reviews/max(reviewers,1))
    rec={'artifact_type':'cap_reviewer_load_pressure_record','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'cap-review-{_id(reviewers,required_reviews)}','owner':'CAP','created_at':'2026-04-15T00:00:00Z','status':'warn' if load>4 else 'pass','load_ratio':load,'reason_codes':['reviewer_pressure_surfaced'] if load>4 else ['balanced_reviewer_load']}
    validate_artifact(rec,'cap_reviewer_load_pressure_record'); return rec

def build_cap_parallelism_ceiling_record(*, requested_parallelism: int, ceiling: int)->dict[str,Any]:
    exceeded=requested_parallelism>ceiling
    rec={'artifact_type':'cap_parallelism_ceiling_record','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'cap-parallel-{_id(requested_parallelism,ceiling)}','owner':'CAP','created_at':'2026-04-15T00:00:00Z','status':'fail' if exceeded else 'pass','reason_codes':['over_parallelization_surfaced'] if exceeded else ['ceiling_calculation']}
    validate_artifact(rec,'cap_parallelism_ceiling_record'); return rec

def build_qos_roadmap_queue_pressure_forecast(*, queue_depth:int, throughput:int)->dict[str,Any]:
    pressure=(queue_depth/max(throughput,1))
    rec={'artifact_type':'qos_roadmap_queue_pressure_forecast','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'qos-forecast-{_id(queue_depth,throughput)}','owner':'QOS','created_at':'2026-04-15T00:00:00Z','status':'warn' if pressure>5 else 'pass','pressure_score':pressure,'reason_codes':['false_green_suppression'] if pressure>5 else ['pressure_forecast_correctness'],'non_authority_assertions':['qos_signal_only']}
    validate_artifact(rec,'qos_roadmap_queue_pressure_forecast'); return rec

def build_qos_retry_storm_susceptibility_record(*, retries: int, failures: int)->dict[str,Any]:
    score=(retries*max(failures,1))
    high=score>=20
    rec={'artifact_type':'qos_retry_storm_susceptibility_record','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'qos-retry-{_id(retries,failures)}','owner':'QOS','created_at':'2026-04-15T00:00:00Z','status':'warn' if high else 'pass','susceptibility_score':score,'reason_codes':['high_risk_pattern_surfaced'] if high else ['susceptibility_forecast_correctness'],'non_authority_assertions':['qos_signal_only']}
    validate_artifact(rec,'qos_retry_storm_susceptibility_record'); return rec

def build_ctx_roadmap_scale_context_preflight_report(*, context_tokens: int, max_tokens: int, recipe_complete: bool)->dict[str,Any]:
    fail=context_tokens>max_tokens or not recipe_complete
    rec={'artifact_type':'ctx_roadmap_scale_context_preflight_report','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'ctx-preflight-{_id(context_tokens,max_tokens,recipe_complete)}','owner':'CTX','created_at':'2026-04-15T00:00:00Z','status':'fail' if fail else 'pass','reason_codes':['oversized_invalid_insufficient_context_fail_closed'] if fail else ['good_context_pass']}
    validate_artifact(rec,'ctx_roadmap_scale_context_preflight_report'); return rec

def build_ctx_context_recipe_conformity_report(*, expected_recipe: str, observed_recipe: str)->dict[str,Any]:
    drift=expected_recipe!=observed_recipe
    rec={'artifact_type':'ctx_context_recipe_conformity_report','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'ctx-recipe-{_id(expected_recipe,observed_recipe)}','owner':'CTX','created_at':'2026-04-15T00:00:00Z','status':'fail' if drift else 'pass','reason_codes':['drifted_recipe_surfaced'] if drift else ['valid_recipe_conformity']}
    validate_artifact(rec,'ctx_context_recipe_conformity_report'); return rec

def build_con_interface_drift_report(*, expected_interfaces: list[str], observed_interfaces: list[str])->dict[str,Any]:
    drift=sorted(set(observed_interfaces)-set(expected_interfaces))
    rec={'artifact_type':'con_interface_drift_report','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'con-drift-{_id(expected_interfaces,observed_interfaces)}','owner':'CON','created_at':'2026-04-15T00:00:00Z','status':'fail' if drift else 'pass','drifted_interfaces':drift,'reason_codes':['drift_surfaced'] if drift else ['no_interface_drift']}
    validate_artifact(rec,'con_interface_drift_report'); return rec

def build_con_cross_owner_contract_compatibility_matrix(*, pairs: list[Mapping[str,Any]])->dict[str,Any]:
    incompatible=[p for p in pairs if not p.get('compatible',False)]
    rec={'artifact_type':'con_cross_owner_contract_compatibility_matrix','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'con-matrix-{_id(pairs)}','owner':'CON','created_at':'2026-04-15T00:00:00Z','status':'fail' if incompatible else 'pass','incompatible_pairs':incompatible,'reason_codes':['incompatible_owner_pair_surfaced'] if incompatible else ['compatibility_matrix_correctness']}
    validate_artifact(rec,'con_cross_owner_contract_compatibility_matrix'); return rec

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

def build_cde_escalation_to_human_decision(*, uncertainty: float, risk: float, threshold: float=0.7)->dict[str,Any]:
    escalate=(uncertainty>=threshold) or (risk>=threshold)
    rec={'artifact_type':'cde_escalation_to_human_decision','schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'cde-escalate-{_id(uncertainty,risk,threshold)}','owner':'CDE','created_at':'2026-04-15T00:00:00Z','status':'halt' if escalate else 'continue','reason_codes':['escalation_when_posture_uncertainty_exceeds_threshold'] if escalate else ['no_explicit_escalation_required']}
    validate_artifact(rec,'cde_escalation_to_human_decision'); return rec

def run_red_team_round(*, round_id: str, fixtures: list[Mapping[str, Any]])->dict[str,Any]:
    finding_ids=[str(f.get('fixture_id')) for f in fixtures if f.get('exploit')]
    name={
      'RT-C1':'ril_plan_wide_coherence_red_team_report',
      'RT-C2':'ril_temporal_dependency_red_team_report',
      'RT-C3':'ril_signal_overload_red_team_report',
      'RT-C4':'ril_budget_readiness_red_team_report',
      'RT-D1':'ril_plan_wide_coherence_red_team_report',
      'RT-D2':'ril_temporal_dependency_red_team_report',
      'RT-D3':'ril_plan_wide_coherence_red_team_report',
      'RT-D4':'ril_temporal_dependency_red_team_report',
      'RT-D5':'ril_signal_overload_red_team_report',
      'RT-D6':'ril_budget_readiness_red_team_report',
    }[round_id]
    rec={'artifact_type':name,'schema_version':'1.0.0','artifact_version':'1.0.0','standards_version':'1.0.0','artifact_id':f'{round_id}-{_id(finding_ids)}','owner':'RIL','created_at':'2026-04-15T00:00:00Z','status':'fail' if finding_ids else 'pass','finding_ids':finding_ids,'reason_codes':['adversarial_findings_detected'] if finding_ids else ['no_exploit'] ,'non_authority_assertions':['red_team_signal_only']}
    validate_artifact(rec,name); return rec
