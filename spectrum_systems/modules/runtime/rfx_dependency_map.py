from __future__ import annotations

def build_rfx_dependency_map(*,modules:list[dict])->dict:
    produced={a for m in modules for a in m.get('produces',[])}
    reason=[]
    deps=[]
    for m in modules:
        name=m.get('module')
        for d in m.get('depends_on_modules',[]):
            deps.append((name,d))
            if d not in {x.get('module') for x in modules}: reason.append('rfx_hidden_dependency_detected')
        if not m.get('owner_refs'): reason.append('rfx_dependency_owner_context_missing')
        for c in m.get('consumes',[]):
            if c not in produced: reason.append('rfx_missing_artifact_producer')
    if any(a==b for a,b in deps): reason.append('rfx_dependency_cycle_detected')
    consumed={c for m in modules for c in m.get('consumes',[])}
    if any(a not in consumed for a in produced): reason.append('rfx_unused_output_artifact')
    return {'artifact_type':'rfx_dependency_map','schema_version':'1.0.0','modules':modules,'dependencies':sorted(deps),'status':'valid' if not reason else 'invalid','reason_codes_emitted':sorted(set(reason)),'signals':{'dependency_count':len(deps),'hidden_dependency_count':reason.count('rfx_hidden_dependency_detected'),'orphan_artifact_count':reason.count('rfx_missing_artifact_producer')}}
