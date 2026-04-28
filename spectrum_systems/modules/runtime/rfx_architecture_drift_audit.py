from __future__ import annotations

def run_rfx_architecture_drift_audit(*,modules:list[dict],bloat_status:dict|None=None)->dict:
    reason=[]
    for m in modules:
        flags=m.get('flags',{})
        if flags.get('hidden_authority'): reason.append('rfx_hidden_authority_detected')
        if flags.get('repo_mutation'): reason.append('rfx_repo_mutation_attempted')
        if flags.get('policy_activation'): reason.append('rfx_policy_activation_attempted')
        if flags.get('roadmap_mutation'): reason.append('rfx_roadmap_mutation_attempted')
        if flags.get('owner_supersession'): reason.append('rfx_owner_supersession_attempted')
    return {'artifact_type':'rfx_architecture_drift_audit','schema_version':'1.0.0','status':'clean' if not reason else 'drifted','reason_codes_emitted':sorted(set(reason)),'module_count':len(modules),'bloat_status':bloat_status or {},'signals':{'hidden_authority_count':reason.count('rfx_hidden_authority_detected'),'mutation_attempt_count':sum(reason.count(x) for x in ['rfx_repo_mutation_attempted','rfx_policy_activation_attempted','rfx_roadmap_mutation_attempted']),'owner_boundary_gap_count':reason.count('rfx_owner_supersession_attempted')}}
