from __future__ import annotations
from typing import Any

REQUIRED=(
'rfx_reason_code_duplicate','rfx_reason_code_missing_owner_context','rfx_reason_code_missing_repair_hint','rfx_reason_code_unregistered','rfx_reason_code_ambiguous',
)
class RFXReasonCodeRegistryError(ValueError):
    pass

def build_rfx_reason_code_registry(*,entries:list[dict[str,Any]],module_exports:dict[str,list[str]]|None=None)->dict[str,Any]:
    module_exports=module_exports or {}
    seen={}
    reason=[]
    normalized=[]
    for e in sorted(entries or [],key=lambda x:(x.get('code',''),x.get('module',''))):
        code=e.get('code')
        if not isinstance(code,str) or not code.strip():
            continue
        code=code.strip()
        meaning=(e.get('failure_prevented') or '').strip()
        if code in seen and seen[code]!=meaning:
            reason.append('rfx_reason_code_ambiguous')
        if code in seen:
            reason.append('rfx_reason_code_duplicate')
        seen[code]=meaning
        if not e.get('owner_context'): reason.append('rfx_reason_code_missing_owner_context')
        if not e.get('repair_hint'): reason.append('rfx_reason_code_missing_repair_hint')
        normalized.append({'code':code,'module':e.get('module'),'owner_context':e.get('owner_context'),'failure_prevented':meaning,'repair_hint':e.get('repair_hint'),'severity':e.get('severity','medium')})
    reg={x['code'] for x in normalized}
    for mod,codes in sorted(module_exports.items()):
        for c in codes:
            if c not in reg: reason.append('rfx_reason_code_unregistered')
    return {'artifact_type':'rfx_reason_code_registry','schema_version':'1.0.0','entries':sorted(normalized,key=lambda x:x['code']),
            'required_reason_codes':list(REQUIRED),'status':'valid' if not reason else 'invalid','reason_codes_emitted':sorted(set(reason)),
            'signals':{'registered_reason_code_count':len(reg),'duplicate_count':reason.count('rfx_reason_code_duplicate'),'missing_hint_count':reason.count('rfx_reason_code_missing_repair_hint')}}
