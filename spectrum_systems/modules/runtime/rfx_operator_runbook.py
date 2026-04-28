from __future__ import annotations

def build_rfx_operator_runbook(*,registry:dict,debug_bundles:list[dict])->dict:
    reason=[];items=[];idx={b.get('reason_code'):b for b in debug_bundles}
    for e in registry.get('entries',[]):
        c=e.get('code')
        b=idx.get(c)
        if not c: reason.append('rfx_runbook_reason_missing'); continue
        if not e.get('repair_hint'): reason.append('rfx_runbook_action_missing')
        if not e.get('owner_context'): reason.append('rfx_runbook_owner_context_missing')
        if not b: reason.append('rfx_runbook_debug_ref_missing')
        items.append({'reason_code':c,'meaning':e.get('failure_prevented'),'likely_cause':e.get('failure_prevented'),'repair_hint':e.get('repair_hint'),'source_module':e.get('module'),'canonical_owner_context':e.get('owner_context'),'related_tests':e.get('test_refs',[]),'escalation_path':e.get('owner_context'),'debug_bundle_ref':b.get('debug_ref') if b else None})
    return {'artifact_type':'rfx_operator_runbook','schema_version':'1.0.0','items':items,'reason_codes_emitted':sorted(set(reason)),'status':'complete' if not reason else 'incomplete','signals':{'runbook_coverage_percentage':100.0 if not reason else 0.0}}
