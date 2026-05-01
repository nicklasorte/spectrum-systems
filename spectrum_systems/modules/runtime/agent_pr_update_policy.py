from __future__ import annotations
import json, hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

REQUIRED_CLP_CHECKS={"authority_shape_preflight","authority_leak_guard","contract_enforcement","tls_generated_artifact_freshness","contract_preflight","selected_tests"}
LEGS=["AEX","PQX","EVL","TPA","CDE","SEL","LIN","REP"]

class PolicyLoadError(ValueError):...

def utc_now_iso()->str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')

def stable_id(work_item_id:str,ts:str)->str:
    return 'agent-pr-update-ready-'+hashlib.sha256(f'{work_item_id}|{ts}'.encode()).hexdigest()[:16]

def load_json(path:Path)->dict[str,Any]|None:
    if not path.is_file(): return None
    try: d=json.loads(path.read_text())
    except Exception: return None
    return d if isinstance(d,dict) else None

def load_policy(path:Path)->dict[str,Any]:
    p=load_json(path)
    if not p: raise PolicyLoadError('policy missing or invalid')
    if p.get('policy_id')!='APU-3LS-01': raise PolicyLoadError('policy_id must be APU-3LS-01')
    return p

def _leg_status(agl:dict[str,Any]|None, leg:str, out_of_scope:set[str])->dict[str,Any]:
    if leg in out_of_scope:
        return {"status":"unknown","reason_codes":["leg_out_of_scope_by_policy"],"artifact_refs":[]}
    legs=((agl or {}).get('loop_legs') or {})
    data=legs.get(leg.lower()) or {}
    status='missing'; refs=[]; reasons=[]
    if data.get('present') is True: status='present'
    elif isinstance(data.get('status'),str): status=data['status']
    refs=[r for r in (data.get('artifact_refs') or data.get('refs') or []) if isinstance(r,str) and r.strip()]
    reasons=[r for r in (data.get('reason_codes') or []) if isinstance(r,str) and r.strip()]
    if status=='present' and not refs:
        status='partial'; reasons = reasons or ['present_without_artifact_refs']
    if status in {'partial','missing','unknown'} and not reasons:
        reasons=['missing_reason_codes']
    return {"status":status,"reason_codes":reasons,"artifact_refs":refs}

def evaluate(policy:dict[str,Any],clp:dict[str,Any]|None,agl:dict[str,Any]|None,repo_mutating:bool|None)->dict[str,Any]:
    reasons=[]; status='ready'
    if repo_mutating is None: status='not_ready'; reasons.append('repo_mutating_unknown')
    if repo_mutating is True:
        if clp is None: status='not_ready'; reasons.append('clp_evidence_missing')
        if agl is None: status='not_ready'; reasons.append('agl_evidence_missing')
    clp_status='missing' if clp is None else str(clp.get('gate_status') or 'unknown')
    allowed=set(policy.get('allowed_warning_reason_codes') or [])
    blocked=[]
    if clp is not None:
        present={str(c.get('check_name')) for c in (clp.get('checks') or []) if isinstance(c,dict)}
        missing=sorted(REQUIRED_CLP_CHECKS-present)
        if missing: status='not_ready'; reasons.append('clp_required_check_classes_missing')
        if clp_status=='block': status='not_ready'; reasons.append('clp_block')
        if clp_status=='warn':
            warns=[]
            for c in clp.get('checks') or []:
                if isinstance(c,dict) and c.get('status')=='warn': warns += [x for x in (c.get('reason_codes') or []) if isinstance(x,str)]
            blocked=[w for w in warns if w not in allowed]
            if blocked: status='not_ready'; reasons.append('clp_warn_reason_code_not_allowed')
    out_of_scope=set(policy.get('optional_legs_out_of_scope') or [])
    evidence={leg:_leg_status(agl,leg,out_of_scope) for leg in LEGS}
    evidence['CLP']={"status":clp_status if clp_status in {'pass','warn','block'} else ('missing' if clp is None else 'unknown'),"artifact_refs":[policy.get('clp_result_ref','')] if clp else [],"reason_codes":([] if clp else ['clp_evidence_missing'])}
    evidence['AGL']={"status":'present' if agl else 'missing',"artifact_refs":[policy.get('agl_result_ref','')] if agl else [],"reason_codes":([] if agl else ['agl_evidence_missing'])}
    evidence['APU']={"status":status,"artifact_refs":[],"reason_codes":reasons[:]}
    for k,v in evidence.items():
        if v['status'] in {'partial','missing','unknown'} and not v['reason_codes']: status='not_ready'; reasons.append(f'{k.lower()}_missing_reason_codes')
        if v['status']=='present' and not v['artifact_refs'] and k not in {'APU'}: status='not_ready'; reasons.append(f'{k.lower()}_present_without_artifact_refs')
    return {"readiness_status":status,"reason_codes":sorted(set(reasons)),"clp_status":clp_status,"blocked_warning_reason_codes":sorted(set(blocked)),"allowed_warning_reason_codes":sorted(allowed),"evidence":evidence}

def build_result(work_item_id:str,agent_type:str,repo_mutating:bool|None,policy_ref:str,clp_ref:str|None,agl_ref:str|None,evaluation:dict[str,Any])->dict[str,Any]:
    ts=utc_now_iso()
    return {"artifact_type":"agent_pr_update_ready_result","schema_version":"1.0.0","created_at":ts,"trace_id":stable_id(work_item_id,ts),"work_item_id":work_item_id,"agent_type":agent_type if agent_type in {'codex','claude','other','unknown'} else 'unknown',"repo_mutating":repo_mutating,"readiness_status":evaluation['readiness_status'],"reason_codes":evaluation['reason_codes'],"evidence":evaluation['evidence'],"clp_status":evaluation['clp_status'],"allowed_warning_reason_codes":evaluation['allowed_warning_reason_codes'],"blocked_warning_reason_codes":evaluation['blocked_warning_reason_codes'],"source_artifact_refs":[r for r in [clp_ref,agl_ref] if r],"policy_ref":policy_ref,"inputs_hash":hashlib.sha256(json.dumps({"repo_mutating":repo_mutating,"source_artifact_refs":[r for r in [clp_ref,agl_ref] if r]},sort_keys=True).encode()).hexdigest(),"authority_scope":"observation_only"}
