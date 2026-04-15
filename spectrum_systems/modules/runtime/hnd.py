"""HND/HNX handoff integrity."""
from __future__ import annotations

def build_handoff_record(*, handoff_id:str, required_keys:list[str], state:dict)->dict:
    missing=[k for k in required_keys if k not in state]
    return {'artifact_type':'handoff_record','artifact_version':'1.0.0','schema_version':'1.0.0','standards_version':'1.9.1','record_id':handoff_id,'owner':'HND','created_at':'2026-04-15T00:00:00Z','status':'blocked' if missing else 'ready','details':{'missing_keys':missing,'state_keys':sorted(state.keys())}}

def emit_resume_record(*, checkpoint_id:str, handoff_record:dict)->dict:
    return {'artifact_type':'resume_record','artifact_version':'1.0.0','schema_version':'1.0.0','resume_id':f'RES-{checkpoint_id}','checkpoint_id':checkpoint_id,'allowed':handoff_record.get('status')=='ready'}
