from __future__ import annotations

def build_rfx_golden_loop_record(*,loop:dict)->dict:
    m=[]
    for k,c in [('failure_ref','rfx_golden_loop_missing_failure'),('eval_ref','rfx_golden_loop_missing_eval'),('fix_proof_ref','rfx_golden_loop_missing_fix_proof'),('trend_ref','rfx_golden_loop_missing_trend'),('recommendation_ref','rfx_golden_loop_missing_recommendation')]:
        if not loop.get(k): m.append(c)
    return {'artifact_type':'rfx_golden_loop_record','schema_version':'1.0.0','links':{k:loop.get(k) for k in ['failure_ref','eval_ref','fix_proof_ref','trend_ref','recommendation_ref','debug_bundle_ref','health_update_ref']},'status':'complete' if not m else 'incomplete','reason_codes_emitted':sorted(set(m)),'signals':{'golden_loop_completion_percentage':100.0 if not m else 0.0}}
