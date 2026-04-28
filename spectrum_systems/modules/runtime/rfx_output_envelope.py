from __future__ import annotations
from typing import Any

VALID_STATUS={'ok','incomplete','blocked'}

def validate_rfx_output_envelope(envelope:dict[str,Any])->list[str]:
    r=[]
    if not envelope.get('artifact_type'): r.append('rfx_envelope_missing_artifact_type')
    if not envelope.get('trace_refs'): r.append('rfx_envelope_missing_trace')
    if 'reason_codes' not in envelope: r.append('rfx_envelope_missing_reason_codes')
    if not envelope.get('producer_module'): r.append('rfx_envelope_missing_producer')
    if envelope.get('status') not in VALID_STATUS: r.append('rfx_envelope_invalid_status')
    return sorted(set(r))

def build_rfx_output_envelope(*,artifact_type:str,producer_module:str,status:str,reason_codes:list[str],trace_refs:list[str],source_refs:list[str],debug_bundle_ref:str|None=None,canonical_owner_refs:list[str]|None=None)->dict[str,Any]:
    e={'artifact_type':artifact_type,'schema_version':'1.0.0','producer_module':producer_module,'phase_label':'RFX','status':status,'reason_codes':reason_codes,'trace_refs':trace_refs,'source_refs':source_refs,'produced_at':'deterministic:runtime-input','debug_bundle_ref':debug_bundle_ref,'canonical_owner_refs':canonical_owner_refs or []}
    e['reason_codes_emitted']=validate_rfx_output_envelope(e)
    e['conformance_percentage']=100.0 if not e['reason_codes_emitted'] else 0.0
    return e
