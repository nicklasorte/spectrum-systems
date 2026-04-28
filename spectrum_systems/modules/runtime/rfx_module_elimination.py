from __future__ import annotations

def evaluate_rfx_module_elimination(*,modules:list[dict])->dict:
    reason=[];recs=[]
    for m in modules:
        impacts=m.get('impacts',[])
        if not impacts:
            reason.append('rfx_module_unjustified'); rec='review'
        elif 'breaks_loop' in impacts:
            reason.append('rfx_module_removal_breaks_loop'); rec='keep'
        elif 'debug_loss' in impacts:
            reason.append('rfx_module_removal_reduces_debuggability'); rec='keep'
        elif 'signal_loss' in impacts:
            reason.append('rfx_module_removal_reduces_signal'); rec='keep'
        else:
            rec='deprecate'
        recs.append({'module':m.get('module'),'recommendation':rec})
    return {'artifact_type':'rfx_module_elimination_result','schema_version':'1.0.0','recommendations':recs,'reason_codes_emitted':sorted(set(reason)),'signals':{'module_justification_coverage':100.0*sum(1 for m in modules if m.get('impacts'))/max(len(modules),1),'removable_module_count':sum(1 for x in recs if x['recommendation']!='keep')}}
