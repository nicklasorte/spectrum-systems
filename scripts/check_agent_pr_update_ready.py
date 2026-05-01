#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.agent_pr_update_policy import load_json,load_policy,evaluate,build_result,PolicyLoadError

def parse():
 p=argparse.ArgumentParser()
 p.add_argument('--work-item-id',required=True)
 p.add_argument('--agent-type',default='unknown',choices=['codex','claude','other','unknown'])
 p.add_argument('--policy',default='docs/governance/agent_pr_update_policy.json')
 p.add_argument('--clp-result',default='outputs/core_loop_pre_pr_gate/core_loop_pre_pr_gate_result.json')
 p.add_argument('--agl-result',default='artifacts/agent_core_loop/agent_core_loop_run_record.json')
 p.add_argument('--repo-mutating',default='auto',choices=['auto','true','false','unknown'])
 p.add_argument('--output',default='outputs/agent_pr_update/agent_pr_update_ready_result.json')
 return p.parse_args()

def main()->int:
 a=parse(); policy_path=(ROOT/a.policy).resolve()
 try: policy=load_policy(policy_path)
 except PolicyLoadError as e:
  print(json.dumps({'error':'policy_load_failed','detail':str(e)})); return 2
 clp_path=(ROOT/a.clp_result).resolve(); agl_path=(ROOT/a.agl_result).resolve()
 clp=load_json(clp_path); agl=load_json(agl_path)
 repo_mut=None if a.repo_mutating in {'auto','unknown'} else (a.repo_mutating=='true')
 if repo_mut is None and clp and isinstance(clp.get('repo_mutating'),bool): repo_mut=clp['repo_mutating']
 policy['clp_result_ref']=str(clp_path.relative_to(ROOT)) if clp_path.exists() else None
 policy['agl_result_ref']=str(agl_path.relative_to(ROOT)) if agl_path.exists() else None
 e=evaluate(policy,clp,agl,repo_mut)
 artifact=build_result(a.work_item_id,a.agent_type,repo_mut,str(policy_path.relative_to(ROOT)),policy.get('clp_result_ref'),policy.get('agl_result_ref'),e)
 validate_artifact(artifact,'agent_pr_update_ready_result')
 out=(ROOT/a.output).resolve(); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(artifact,indent=2)+'\n')
 print(json.dumps({'readiness_status':artifact['readiness_status'],'reason_codes':artifact['reason_codes'],'output':str(out.relative_to(ROOT))},indent=2))
 return 0 if artifact['readiness_status']=='ready' else 2
if __name__=='__main__': raise SystemExit(main())
