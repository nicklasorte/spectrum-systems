from __future__ import annotations
import json,hashlib
from typing import Any

RFX_HEALTH_REQUIRED_CODES=(
    'rfx_health_module_missing','rfx_health_reason_code_missing','rfx_health_artifact_missing','rfx_health_owner_ref_missing','rfx_health_test_ref_missing',
)

class RFXHealthContractError(ValueError):
    pass

def _sid(payload: Any,prefix:str)->str:
    c=json.dumps(payload,sort_keys=True,separators=(',',':'))
    return f"{prefix}-{hashlib.sha256(c.encode()).hexdigest()[:12]}"

def build_rfx_health_contract(*,modules:list[dict[str,Any]])->dict[str,Any]:
    missing=[]
    valid=[]
    for m in modules or []:
        if not isinstance(m,dict):
            continue
        name=m.get('module')
        if not isinstance(name,str) or not name.strip():
            missing.append('rfx_health_module_missing');continue
        if not m.get('reason_codes'): missing.append('rfx_health_reason_code_missing')
        if not m.get('artifact_types'): missing.append('rfx_health_artifact_missing')
        if not m.get('owner_refs'): missing.append('rfx_health_owner_ref_missing')
        if not m.get('test_refs'): missing.append('rfx_health_test_ref_missing')
        valid.append(m)
    total=max(len(modules or []),1)
    complete=max(total-len(missing),0)
    return {
        'artifact_type':'rfx_health_contract','schema_version':'1.0.0','contract_id':_sid(modules or [],'rfx-health'),
        'modules':sorted(valid,key=lambda x:x.get('module','')),
        'reason_codes':sorted(set(RFX_HEALTH_REQUIRED_CODES)),
        'coverage_signals':{
            'rfx_coverage_completeness_percentage':round(100.0*len(valid)/total,2),
            'reason_code_coverage_percentage':round(100.0*(1.0 if not missing else 0.0),2),
            'module_debug_readiness_percentage':round(100.0*sum(1 for m in valid if m.get('debug_bundle_available'))/max(len(valid),1),2),
        },
        'known_risks':[m.get('known_risks',[]) for m in valid],
        'red_team_coverage':[m.get('red_team_refs',[]) for m in valid],
        'status':'healthy' if not missing else 'incomplete',
        'reason_codes_emitted':sorted(set(missing)),
    }
