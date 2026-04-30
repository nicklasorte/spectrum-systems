from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

MAX_ATTEMPTS=2
KNOWN_CLASSES={"authority_shape_violation","authority_leak_guard_failure","pytest_selection_missing","schema_validation_failure","contract_enforcement_failure","missing_shard_artifact","invalid_shard_artifact","pr_gate_block","dashboard_test_failure","unknown_failure"}
AUTO_REPAIR_CLASSES={"authority_shape_violation","authority_leak_guard_failure","pytest_selection_missing","schema_validation_failure"}


def _now()->str:
    return datetime.now(timezone.utc).isoformat()

def _load(path:Path)->dict[str,Any]|None:
    if not path.is_file(): return None
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None
    return data if isinstance(data,dict) else None

def observe_failures(pr_number:int, repo:str, head_sha:str, attempt_number:int, input_dir:Path)->dict[str,Any]:
    if attempt_number not in (1,2):
        raise ValueError('attempt_number must be 1 or 2')
    artifacts=[]; reason_codes=[]
    paths=[
      input_dir/'pr_gate'/'pr_gate_result.json',
      input_dir/'authority_shape_preflight'/'authority_shape_preflight_result.json',
      input_dir/'authority_leak_guard'/'authority_leak_guard_result.json',
      input_dir/'contract_preflight'/'contract_preflight_result_artifact.json',
    ]
    for p in paths:
      d=_load(p)
      if d is not None:
        artifacts.append(str(p))
        status=str(d.get('status','')).lower()
        if status in {'fail','failed','block','blocked'}:
          reason_codes.append(f'{p.stem}:{status}')
    if not artifacts:
      reason_codes.append('ci_failure_logs_missing')
    return {
      'artifact_type':'pr_ci_failure_observation_record','schema_version':'1.0.0','pr_number':pr_number,'repo':repo,'head_sha':head_sha,'attempt_number':attempt_number,'max_attempts':MAX_ATTEMPTS,
      'source_artifacts_used':artifacts,'trace_refs':['AEX:admission','PQX:pending','EVL:pending','TPA:pending','CDE:pending','SEL:pending'],'reason_codes':reason_codes,
      'authority_scope':'observation_only','observed_at':_now(),'ci_failure_logs_present':bool(artifacts)
    }

def normalize_failure(obs:dict[str,Any])->dict[str,Any]:
    class_name='unknown_failure'; affected=[]
    joined=' '.join(obs.get('reason_codes',[]))
    mapping=[('authority_shape','authority_shape_violation'),('authority_leak','authority_leak_guard_failure'),('pr_gate','pr_gate_block'),('contract_preflight','contract_enforcement_failure')]
    for k,v in mapping:
      if k in joined: class_name=v
    if class_name=='unknown_failure':
      next_action='human_review_required'
    else:
      next_action='propose_bounded_repair'
    return {
      'artifact_type':'pr_failure_normalization_packet','schema_version':'1.0.0','pr_number':obs['pr_number'],'repo':obs['repo'],'head_sha':obs['head_sha'],'attempt_number':obs['attempt_number'],'max_attempts':MAX_ATTEMPTS,
      'source_artifacts_used':obs['source_artifacts_used'],'trace_refs':obs['trace_refs'],'reason_codes':obs['reason_codes'],'authority_scope':'observation_only',
      'failure_class':class_name,'affected_files':affected,'next_action':next_action,'human_review_required':class_name=='unknown_failure'
    }

def build_candidate(norm:dict[str,Any])->dict[str,Any]:
    fc=norm['failure_class']
    human= fc not in AUTO_REPAIR_CLASSES
    bounded=['docs/governance/pytest_pr_selection_integrity_policy.json'] if fc=='pytest_selection_missing' else ['contracts/examples'] if fc=='schema_validation_failure' else ['docs/architecture/system_registry.md'] if fc.startswith('authority_') else []
    return {'artifact_type':'pr_repair_candidate_record','schema_version':'1.0.0','pr_number':norm['pr_number'],'repo':norm['repo'],'head_sha':norm['head_sha'],'attempt_number':norm['attempt_number'],'max_attempts':MAX_ATTEMPTS,
    'source_artifacts_used':norm['source_artifacts_used'],'trace_refs':norm['trace_refs'],'reason_codes':norm['reason_codes'],'authority_scope':'observation_only',
    'failure_class':fc,'bounded_files':bounded,'forbidden_files':['.github/workflows','tests','contracts/schemas'],'allowed_operations':['update_text_only'],'tests_required':['python -m pytest -q'],
    'risk_level':'low' if not human else 'high','human_review_required':human,'repair_plan':'bounded deterministic repair only'}

def authorize(candidate:dict[str,Any])->dict[str,Any]:
    n=candidate['attempt_number']
    status='allow_repair'
    if n>MAX_ATTEMPTS: status='blocked'
    if candidate['human_review_required']: status='human_review_required'
    return {'artifact_type':'pr_repair_authorization_record','schema_version':'1.0.0','pr_number':candidate['pr_number'],'repo':candidate['repo'],'head_sha':candidate['head_sha'],'attempt_number':n,'max_attempts':MAX_ATTEMPTS,
    'source_artifacts_used':candidate['source_artifacts_used'],'trace_refs':candidate['trace_refs'],'reason_codes':candidate['reason_codes'],'authority_scope':'observation_only',
    'authorization_status':status,'authorized_files':candidate['bounded_files'],'repair_candidate_ref':'pr_repair_candidate_record'}

def execute_repair(candidate:dict[str,Any], auth:dict[str,Any], apply_repair:bool=False)->dict[str,Any]:
    status='blocked'; changed=[];cmd=[];tests=[]
    if auth['authorization_status']=='allow_repair' and apply_repair:
      status='completed';cmd=['bounded repair simulated'];tests=['python -m pytest tests/test_pr_repair_loop.py -q']
    return {'artifact_type':'pr_repair_execution_record','schema_version':'1.0.0','pr_number':candidate['pr_number'],'repo':candidate['repo'],'head_sha':candidate['head_sha'],'attempt_number':candidate['attempt_number'],'max_attempts':MAX_ATTEMPTS,
    'source_artifacts_used':candidate['source_artifacts_used'],'trace_refs':candidate['trace_refs'],'reason_codes':candidate['reason_codes'],'authority_scope':'observation_only',
    'files_changed':changed,'commands_run':cmd,'tests_run':tests,'pqx_execution_ref':'PQX:execution','evl_result_refs':['EVL:evaluation'],'authority_preflight_refs':['TPA:scope_check','CDE:decision_input','SEL:gate_input'],'tests_weakened':False,'skipped_required_gate':False,'status':status}

def summarize(obs,norm,candidate,auth,exec_rec):
    failed = exec_rec['status']!='completed'
    human = norm['human_review_required'] or (obs['attempt_number']==2 and failed)
    status='human_review_required' if human else 'completed'
    return {'artifact_type':'pr_repair_attempt_summary_record','schema_version':'1.0.0','pr_number':obs['pr_number'],'repo':obs['repo'],'head_sha':obs['head_sha'],'attempt_number':obs['attempt_number'],'max_attempts':MAX_ATTEMPTS,'source_artifacts_used':obs['source_artifacts_used'],'trace_refs':obs['trace_refs'],'reason_codes':obs['reason_codes'],'authority_scope':'observation_only','status':status,'human_review_required':human,'remaining_failure':norm['failure_class'],'next_manual_action':'operator triage required' if human else 'none'}
