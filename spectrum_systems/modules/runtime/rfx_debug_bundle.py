from __future__ import annotations
from typing import Any

class RFXDebugBundleError(ValueError):
    pass

def build_rfx_debug_bundle(*,failure:dict[str,Any])->dict[str,Any]:
    r=[]
    if not failure.get('reason_codes'): r.append('rfx_debug_reason_missing')
    if not failure.get('source_refs'): r.append('rfx_debug_source_ref_missing')
    if not failure.get('repair_hint'): r.append('rfx_debug_repair_hint_missing')
    if not failure.get('owner_context'): r.append('rfx_debug_owner_context_missing')
    if not failure.get('repro_payload'): r.append('rfx_debug_repro_payload_missing')
    return {'artifact_type':'rfx_debug_bundle','schema_version':'1.0.0','failed_module':failure.get('failed_module'),'failed_helper':failure.get('failed_helper'),'reason_codes':failure.get('reason_codes',[]),
            'source_refs':failure.get('source_refs',[]),'expected_owner_ref':failure.get('owner_context'),'observed_evidence':failure.get('observed_evidence',[]),'missing_evidence':failure.get('missing_evidence',[]),
            'next_repair_hint':failure.get('repair_hint'),'minimal_reproduction_payload':failure.get('repro_payload'),'related_test_refs':failure.get('test_refs',[]),'authority_boundary_note':'RFX supplies evidence only','status':'complete' if not r else 'incomplete','reason_codes_emitted':sorted(set(r)),
            'signals':{'debug_bundle_completeness_percentage':100.0 if not r else 0.0,'mean_time_to_locate_failure_input':'deterministic_placeholder'}}
