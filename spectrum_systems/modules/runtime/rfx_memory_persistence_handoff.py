from __future__ import annotations

def build_rfx_memory_persistence_handoff(*,request:dict)->dict:
    r=[]
    if not request.get('target_owner_ref'): r.append('rfx_memory_persistence_owner_missing')
    if not request.get('lineage_refs'): r.append('rfx_memory_persistence_lineage_missing')
    if request.get('direct_write') and not request.get('trace_ref'): r.append('rfx_untraced_memory_write')
    if request.get('handoff_valid') is False: r.append('rfx_memory_persistence_handoff_invalid')
    return {'artifact_type':'rfx_memory_persistence_handoff','schema_version':'1.0.0','target_owner_ref':request.get('target_owner_ref'),'lineage_refs':request.get('lineage_refs',[]),'trace_ref':request.get('trace_ref'),'status':'valid' if not r else 'invalid','reason_codes_emitted':sorted(set(r)),'signals':{'persistence_handoff_coverage_percentage':100.0 if not r else 0.0}}
