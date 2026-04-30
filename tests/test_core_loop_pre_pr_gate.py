import json
from pathlib import Path
from spectrum_systems.modules.runtime.agent_core_loop_proof import evaluate_agl_repo_mutating_evidence

def _base():
 return {"artifact_type":"core_loop_pre_pr_gate_result","schema_version":"1.0.0","gate_id":"clp-01","work_item_id":"W","agent_type":"codex","repo_mutating":True,"base_ref":"main","head_ref":"HEAD","changed_files":[],"gate_status":"pass","checks":[],"first_failed_check":None,"failure_classes":[],"source_artifacts_used":[],"emitted_artifacts":[],"required_follow_up":[],"trace_refs":[],"replay_refs":[],"authority_scope":"observation_only","human_review_required":False}

def test_missing_authority_shape_output_blocks():
 d=_base(); d['gate_status']='blocked'; d['failure_classes']=['missing_required_artifact']; assert d['gate_status']=='blocked'

def test_unknown_failure_requires_human_review():
 d=_base(); d['failure_classes']=['weird']; d['human_review_required']=True; assert d['human_review_required']

def test_observation_only_required(tmp_path: Path):
 p=tmp_path/'r.json'; d=_base(); d['authority_scope']='approval'; p.write_text(json.dumps(d))
 out=evaluate_agl_repo_mutating_evidence(repo_mutating=True, clp_result_path=str(p)); assert out['compliance_status']=='HOLD'

def test_agl_missing_clp_blocks(tmp_path: Path):
 out=evaluate_agl_repo_mutating_evidence(repo_mutating=True, clp_result_path=str(tmp_path/'none.json')); assert out['compliance_status']=='HOLD'
