from __future__ import annotations

def assess_rfx_bloat_budget(*,measurement:dict,budget:dict)->dict:
    r=[]
    if measurement.get('runtime_ms',0)>budget.get('max_runtime_ms',10**9): r.append('rfx_runtime_budget_exceeded')
    if measurement.get('artifact_size_bytes',0)>budget.get('max_artifact_size_bytes',10**9): r.append('rfx_artifact_size_budget_exceeded')
    if measurement.get('reason_code_count',0)>budget.get('max_reason_code_count',10**9): r.append('rfx_reason_code_budget_exceeded')
    if measurement.get('debug_bundle_size_bytes',0)>budget.get('max_debug_bundle_size_bytes',10**9): r.append('rfx_debug_bundle_too_large')
    if measurement.get('nested_depth',0)>budget.get('max_nested_depth',10**9): r.append('rfx_nested_payload_too_deep')
    return {'artifact_type':'rfx_bloat_budget_record','schema_version':'1.0.0','measurement':measurement,'budget':budget,'status':'within_budget' if not r else 'budget_exceeded','reason_codes_emitted':sorted(set(r)),'signals':{k:measurement.get(k,0) for k in ['runtime_ms','artifact_size_bytes','reason_code_count','debug_bundle_size_bytes']}}
