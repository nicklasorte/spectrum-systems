from __future__ import annotations
import json
from pathlib import Path

CORE=["AEX","PQX","EVL","TPA","CDE","SEL"]
OVER=["LIN","REP","OBS","SLO"]


def _mk(status, refs=None, reasons=None, confidence="medium"):
    return {"status":status,"artifact_refs":refs or [],"reason_codes":reasons or ([] if status=="present" else ["evidence_missing"]),"confidence":confidence}


def build_agent_core_loop_record(work_item_id:str,agent_type:str="unknown",source_artifact:str|None=None)->dict:
    refs=[r for r in [source_artifact,"artifacts/dashboard_metrics/ai_programming_governed_path_record.json","artifacts/dashboard_metrics/governance_violation_record.json"] if r]
    legs={k:_mk("unknown",[],["not_observed"],"low") for k in CORE}
    overlays={k:_mk("unknown",[],["not_observed"],"low") for k in OVER}
    repo_mutating=True
    if source_artifact and Path(source_artifact).exists():
        data=json.loads(Path(source_artifact).read_text(encoding="utf-8"))
        for leg in CORE:
            status=((data.get("core_loop_compliance",{}).get(leg) or {}).get("status") if isinstance(data,dict) else None)
            if status in {"present","partial","missing","unknown"}:
                legs[leg]=_mk(status,(data.get("core_loop_compliance",{}).get(leg) or {}).get("artifact_refs",[]),(data.get("core_loop_compliance",{}).get(leg) or {}).get("reason_codes",[]),"medium")
    first_missing=next((k for k in CORE if legs[k]["status"] in {"missing","unknown"}),None)
    first_failed=next((k for k in CORE if legs[k]["status"]=="failed"),None)
    complete=all(legs[k]["status"]=="present" and legs[k]["artifact_refs"] for k in CORE)
    compliance="PASS" if complete else "WARN"
    if repo_mutating and any(legs[k]["status"] in {"missing","unknown"} for k in ["AEX","PQX"]):
        compliance="BLOCK"
    elif repo_mutating and any(legs[k]["status"] in {"missing","unknown"} for k in ["EVL","TPA","CDE","SEL"]):
        compliance="BLOCK"
    actions=[]
    if compliance!="PASS":
        for leg in CORE:
            if legs[leg]["status"] in {"missing","partial","failed","unknown"}:
                actions.append({"owner_system":leg,"action_type":"add_eval_case" if leg=="EVL" else "add_repair_pattern","reason_code":legs[leg]["reason_codes"][0],"source_failure_ref":refs[0] if refs else "artifacts/unknown.json","recommended_artifact":f"artifacts/{leg.lower()}_evidence.json"})
                break
    return {"artifact_type":"agent_core_loop_run_record","schema_version":"1.0.0","work_item_id":work_item_id,"agent_type":agent_type if agent_type in {"codex","claude","other","unknown"} else "unknown","repo_mutating":repo_mutating,"source_refs":refs,"changed_surfaces":[],"loop_legs":legs,"overlays":overlays,"first_missing_leg":first_missing,"first_failed_leg":first_failed,"core_loop_complete":complete,"compliance_status":compliance,"learning_actions":actions,"trace_refs":[],"replay_refs":[],"authority_scope":"observation_only"}
