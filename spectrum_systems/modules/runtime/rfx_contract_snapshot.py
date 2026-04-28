from __future__ import annotations

def compare_rfx_contract_snapshot(*,current:list[dict],manifest:dict, migration_note:str|None=None)->dict:
    reason=[]
    m=manifest.get('contracts',{})
    for c in current:
        mod=c.get('module')
        old=m.get(mod)
        if not old: continue
        if c.get('artifact_type')!=old.get('artifact_type'): reason.append('rfx_contract_snapshot_mismatch')
        if set(old.get('fields',[]))-set(c.get('fields',[])): reason.append('rfx_contract_field_removed')
        if set(old.get('reason_codes',[]))-set(c.get('reason_codes',[])): reason.append('rfx_contract_reason_removed')
    if reason and not migration_note: reason.append('rfx_contract_migration_missing')
    return {'artifact_type':'rfx_contract_snapshot_result','schema_version':'1.0.0','status':'match' if not reason else 'mismatch','reason_codes_emitted':sorted(set(reason)),'signals':{'contract_drift_count':len(set(reason))},'manifest':manifest}
