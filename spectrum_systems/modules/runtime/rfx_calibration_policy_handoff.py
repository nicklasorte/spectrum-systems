from __future__ import annotations

def build_rfx_calibration_policy_handoff(*,calibration_input:dict)->dict:
    r=[]
    if not calibration_input.get('policy_ref'): r.append('rfx_calibration_policy_ref_missing')
    if calibration_input.get('threshold_source')=='hardcoded': r.append('rfx_calibration_threshold_hardcoded')
    if not calibration_input.get('eval_ref'): r.append('rfx_calibration_eval_ref_missing')
    if calibration_input.get('needs_change') and not calibration_input.get('handoff_ref'): r.append('rfx_calibration_policy_handoff_missing')
    return {'artifact_type':'rfx_calibration_policy_handoff','schema_version':'1.0.0','policy_ref':calibration_input.get('policy_ref'),'eval_ref':calibration_input.get('eval_ref'),'handoff_ref':calibration_input.get('handoff_ref'),'reason_codes_emitted':sorted(set(r)),'status':'valid' if not r else 'invalid','signals':{'calibration_policy_reference_coverage':100.0 if calibration_input.get('policy_ref') else 0.0}}
