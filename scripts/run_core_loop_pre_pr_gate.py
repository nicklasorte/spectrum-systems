#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, subprocess
from pathlib import Path

REQ=["authority_shape_preflight","authority_leak_guard","contract_enforcement","tls_generated_artifact_freshness","contract_preflight","selected_tests"]
KNOWN={"none","authority_shape_violation","authority_leak_guard_failure","contract_enforcement_failure","stale_tls_generated_artifact","contract_preflight_block","selected_tests_failure","missing_required_artifact"}

def run(cmd):
 p=subprocess.run(cmd,shell=True,capture_output=True,text=True)
 return p.returncode,p.stdout+p.stderr

def main():
 a=argparse.ArgumentParser();a.add_argument('--work-item-id',required=True);a.add_argument('--agent-type',default='unknown');a.add_argument('--base-ref',default='main');a.add_argument('--head-ref',default='HEAD');a.add_argument('--output-dir',default='outputs/core_loop_pre_pr_gate');a.add_argument('--execution-context',default='pqx_governed');a.add_argument('--max-repair-attempts',type=int,default=0);args=a.parse_args()
 out=Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
 checks=[]
 def add(n,owner,cmd,rc,outref,fclass='none',reasons=None):
  checks.append({"check_name":n,"owner_system":owner,"command":cmd,"status":"pass" if rc==0 else "block","output_ref":outref,"failure_class":fclass if rc else "none","reason_codes":reasons or ([] if rc==0 else [fclass]),"next_action":"repair" if rc else "continue"})
 add('authority_shape_preflight','AEX',f'python scripts/run_authority_shape_preflight.py --base-ref {args.base_ref} --head-ref {args.head_ref} --suggest-only --output outputs/authority_shape_preflight/authority_shape_preflight_result.json',*((*run(f'python scripts/run_authority_shape_preflight.py --base-ref {args.base_ref} --head-ref {args.head_ref} --suggest-only --output outputs/authority_shape_preflight/authority_shape_preflight_result.json'), 'outputs/authority_shape_preflight/authority_shape_preflight_result.json','authority_shape_violation')))
 add('authority_leak_guard','TPA',f'python scripts/run_authority_leak_guard.py --base-ref {args.base_ref} --head-ref {args.head_ref} --output outputs/authority_leak_guard/authority_leak_guard_result.json',*((*run(f'python scripts/run_authority_leak_guard.py --base-ref {args.base_ref} --head-ref {args.head_ref} --output outputs/authority_leak_guard/authority_leak_guard_result.json'),'outputs/authority_leak_guard/authority_leak_guard_result.json','authority_leak_guard_failure')))
 add('contract_enforcement','EVL','python scripts/run_contract_enforcement.py',*((*run('python scripts/run_contract_enforcement.py'),'docs/governance-reports/contract-compliance-report.md','contract_enforcement_failure')))
 rc1,_=run('python scripts/build_tls_dependency_priority.py'); rc2,_=run('python scripts/generate_ecosystem_health_report.py')
 add('tls_generated_artifact_freshness','LIN','python scripts/build_tls_dependency_priority.py && python scripts/generate_ecosystem_health_report.py',1 if (rc1 or rc2) else 0,'artifacts/tls/','stale_tls_generated_artifact')
 run(f'python scripts/build_preflight_pqx_wrapper.py --base-ref {args.base_ref} --head-ref {args.head_ref}')
 add('contract_preflight','EVL',f'python scripts/run_contract_preflight.py --base-ref {args.base_ref} --head-ref {args.head_ref} --execution-context {args.execution_context}',*((*run(f'python scripts/run_contract_preflight.py --base-ref {args.base_ref} --head-ref {args.head_ref} --execution-context {args.execution_context}'),'outputs/contract_preflight/contract_preflight_result.json','contract_preflight_block')))
 add('selected_tests','EVL','python -m pytest tests/test_core_loop_pre_pr_gate.py -q',*((*run('python -m pytest tests/test_core_loop_pre_pr_gate.py -q'),'outputs/core_loop_pre_pr_gate/selected_tests.log','selected_tests_failure')))
 missing=[c['check_name'] for c in checks if not c['output_ref']]
 failures=[c['failure_class'] for c in checks if c['status']=='block']
 unknown=[f for f in failures if f not in KNOWN]
 status='pass' if not failures and not missing else 'block'
 r={"artifact_type":"core_loop_pre_pr_gate_result","schema_version":"1.0.0","gate_id":"clp-01","work_item_id":args.work_item_id,"agent_type":args.agent_type,"repo_mutating":True,"base_ref":args.base_ref,"head_ref":args.head_ref,"changed_files":[],"gate_status":status,"checks":checks,"first_failed_check":next((c['check_name'] for c in checks if c['status']=='block'),None),"failure_classes":sorted(set(failures+(["missing_required_artifact"] if missing else []))),"source_artifacts_used":[c['output_ref'] for c in checks],"emitted_artifacts":[str(out/'core_loop_pre_pr_gate_result.json')],"required_follow_up":missing,"trace_refs":[],"replay_refs":[],"authority_scope":"observation_only","human_review_required":bool(unknown)}
 (out/'core_loop_pre_pr_gate_result.json').write_text(json.dumps(r,indent=2)+'\n')
 return 1 if status=='block' else 0

if __name__=='__main__': raise SystemExit(main())
