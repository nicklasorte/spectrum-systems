#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
from spectrum_systems.modules.runtime.pr_repair_loop import observe_failures,normalize_failure,build_candidate,prepare_repair_readiness,execute_repair,summarize

def main()->int:
 p=argparse.ArgumentParser()
 p.add_argument('--pr-number',type=int,required=True);p.add_argument('--repo',required=True);p.add_argument('--base-ref',required=True);p.add_argument('--head-ref',required=True)
 p.add_argument('--attempt-number',type=int,required=True);p.add_argument('--max-attempts',type=int,default=2);p.add_argument('--input-dir',required=True);p.add_argument('--output-dir',required=True)
 p.add_argument('--apply-repair',action='store_true')
 a=p.parse_args()
 if a.max_attempts!=2: raise SystemExit('max-attempts must be 2')
 out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True)
 obs=observe_failures(a.pr_number,a.repo,a.head_ref,a.attempt_number,Path(a.input_dir))
 norm=normalize_failure(obs);cand=build_candidate(norm);auth=prepare_repair_readiness(cand);exe=execute_repair(cand,auth,a.apply_repair);summ=summarize(obs,norm,cand,auth,exe)
 for n,o in [('pr_ci_failure_observation_record.json',obs),('pr_failure_normalization_packet.json',norm),('pr_repair_candidate_record.json',cand),('pr_repair_readiness_record.json',auth),('pr_repair_execution_record.json',exe),('pr_repair_attempt_summary_record.json',summ)]:
  (out/n).write_text(json.dumps(o,indent=2),encoding='utf-8')
 return 1 if summ['human_review_required'] else 0
if __name__=='__main__': raise SystemExit(main())
