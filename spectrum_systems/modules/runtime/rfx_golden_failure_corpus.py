from __future__ import annotations

def build_rfx_golden_failure_corpus(*,cases:list[dict],registered_case_ids:set[str]|None=None)->dict:
    registered_case_ids=registered_case_ids or set()
    reason=[]
    for c in cases:
        if not c.get('id'): reason.append('rfx_golden_case_missing')
        if c.get('id') not in registered_case_ids: reason.append('rfx_golden_case_unregistered')
        if not c.get('trace_ref'): reason.append('rfx_golden_case_trace_missing')
        if c.get('actual')!=c.get('expected'): reason.append('rfx_golden_expected_outcome_mismatch')
    return {'artifact_type':'rfx_golden_failure_corpus','schema_version':'1.0.0','cases':cases,'reason_codes_emitted':sorted(set(reason)),'status':'stable' if not reason else 'drifted','signals':{'golden_corpus_coverage_percentage':100.0 if not reason else 0.0,'expected_outcome_stability':1.0 if not reason else 0.0}}
