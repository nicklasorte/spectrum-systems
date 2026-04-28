from __future__ import annotations

def cluster_rfx_reason_codes(*,reasons:list[str],alias_map:dict[str,str]|None=None)->dict:
    alias_map=alias_map or {}
    clusters={}
    reason=[]
    amb=[]
    for r in reasons:
        key=''.join(ch for ch in r.lower() if ch.isalnum() or ch=='_')
        if r in alias_map: key=alias_map[r]
        elif '_' in r and key not in alias_map.values():
            amb.append({'reason':r,'normalized':key})
        if not key: reason.append('rfx_reason_alias_missing'); continue
        clusters.setdefault(key,[]).append(r)
    if amb: reason.append('rfx_reason_cluster_ambiguous')
    if any(len(v)>1 for v in clusters.values()): reason.append('rfx_reason_variant_clustered')
    if any(not v for v in clusters.values()): reason.append('rfx_cluster_evidence_missing')
    return {'artifact_type':'rfx_trend_cluster_record','schema_version':'1.0.0','clusters':dict(sorted(clusters.items())),'ambiguity_record':{'artifact_type':'rfx_trend_ambiguity_record','items':amb},'reason_codes_emitted':sorted(set(reason)),'signals':{'clustered_variant_count':sum(1 for v in clusters.values() if len(v)>1),'ambiguity_count':len(amb),'recurrence_detection_confidence':1.0 if not amb else 0.5}}
