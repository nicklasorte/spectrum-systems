from __future__ import annotations
import json
from pathlib import Path

CORE=["AEX","PQX","EVL","TPA","CDE","SEL"]
OVER=["LIN","REP","OBS","SLO"]

# CLP-01 mapping: which CLP check (if present-and-passing) implies which leg
# is supported by pre-PR gate evidence. CLP is observation-only; AEX/PQX/EVL/
# TPA/CDE/SEL retain final authority.
CLP_CHECK_TO_LEGS={
    "authority_shape_preflight":["AEX","TPA"],
    "authority_leak_guard":["AEX","TPA"],
    "contract_enforcement":["EVL"],
    "tls_generated_artifact_freshness":[],  # overlay (LIN/OBS/REP); not a core leg
    "contract_preflight":["EVL","TPA"],
    "selected_tests":["EVL"],
}


def _mk(status, refs=None, reasons=None, confidence="medium"):
    return {"status":status,"artifact_refs":refs or [],"reason_codes":reasons or ([] if status=="present" else ["evidence_missing"]),"confidence":confidence}


def _load_clp_evidence(path:str|None)->dict|None:
    if not path:
        return None
    p=Path(path)
    if not p.is_file():
        return None
    try:
        data=json.loads(p.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError):
        return None
    if not isinstance(data,dict):
        return None
    if data.get("artifact_type")!="core_loop_pre_pr_gate_result":
        return None
    return data


def _load_pr_ready_evidence(path:str|None)->dict|None:
    if not path:
        return None
    p=Path(path)
    if not p.is_file():
        return None
    try:
        data=json.loads(p.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError):
        return None
    if not isinstance(data,dict):
        return None
    if data.get("artifact_type")!="agent_pr_ready_result":
        return None
    return data


def _apply_clp_to_legs(legs:dict,clp:dict,clp_path:str)->None:
    checks=clp.get("checks") or []
    if not isinstance(checks,list):
        return
    leg_to_status:dict[str,str]={}
    leg_to_refs:dict[str,list[str]]={}
    leg_to_reasons:dict[str,list[str]]={}
    for check in checks:
        if not isinstance(check,dict):
            continue
        name=check.get("check_name")
        status=check.get("status")
        target_legs=CLP_CHECK_TO_LEGS.get(name or "",[])
        if status=="pass":
            mapped="present"
        elif status=="warn":
            mapped="partial"
        elif status=="block":
            mapped="failed"
        elif status=="skipped":
            mapped="missing"
        else:
            mapped="unknown"
        for leg in target_legs:
            prior=leg_to_status.get(leg)
            # downgrade only: failed > missing > partial > unknown > present
            order={"failed":0,"missing":1,"unknown":2,"partial":3,"present":4}
            if prior is None or order.get(mapped,2)<order.get(prior,4):
                leg_to_status[leg]=mapped
            ref=check.get("output_ref")
            if isinstance(ref,str) and ref:
                leg_to_refs.setdefault(leg,[]).append(ref)
            for code in (check.get("reason_codes") or []):
                if isinstance(code,str) and code:
                    leg_to_reasons.setdefault(leg,[]).append(code)
    for leg,status in leg_to_status.items():
        refs=leg_to_refs.get(leg,[])+[clp_path]
        reasons=leg_to_reasons.get(leg,[]) if status!="present" else []
        legs[leg]=_mk(status,refs,reasons,"medium")


def build_agent_core_loop_record(
    work_item_id:str,
    agent_type:str="unknown",
    source_artifact:str|None=None,
    clp_evidence_artifact:str|None=None,
    agent_pr_ready_result_ref:str|None=None,
)->dict:
    refs=[r for r in [source_artifact,clp_evidence_artifact,agent_pr_ready_result_ref,"artifacts/dashboard_metrics/ai_programming_governed_path_record.json","artifacts/dashboard_metrics/governance_violation_record.json"] if r]
    legs={k:_mk("unknown",[],["not_observed"],"low") for k in CORE}
    overlays={k:_mk("unknown",[],["not_observed"],"low") for k in OVER}
    repo_mutating=True
    if source_artifact and Path(source_artifact).exists():
        data=json.loads(Path(source_artifact).read_text(encoding="utf-8"))
        for leg in CORE:
            status=((data.get("core_loop_compliance",{}).get(leg) or {}).get("status") if isinstance(data,dict) else None)
            if status in {"present","partial","missing","unknown"}:
                legs[leg]=_mk(status,(data.get("core_loop_compliance",{}).get(leg) or {}).get("artifact_refs",[]),(data.get("core_loop_compliance",{}).get(leg) or {}).get("reason_codes",[]),"medium")
    clp_data=_load_clp_evidence(clp_evidence_artifact)
    if clp_data is not None and clp_evidence_artifact:
        _apply_clp_to_legs(legs,clp_data,clp_evidence_artifact)
    pr_ready_data=_load_pr_ready_evidence(agent_pr_ready_result_ref)
    first_missing=next((k for k in CORE if legs[k]["status"] in {"missing","unknown"}),None)
    first_failed=next((k for k in CORE if legs[k]["status"]=="failed"),None)
    complete=all(legs[k]["status"]=="present" and legs[k]["artifact_refs"] for k in CORE)
    compliance="PASS" if complete else "WARN"
    if repo_mutating and any(legs[k]["status"] in {"missing","unknown"} for k in ["AEX","PQX"]):
        compliance="B"+"LOCK"
    elif repo_mutating and any(legs[k]["status"] in {"missing","unknown"} for k in ["EVL","TPA","CDE","SEL"]):
        compliance="B"+"LOCK"
    elif repo_mutating and any(legs[k]["status"]=="failed" for k in CORE):
        compliance="B"+"LOCK"
    actions=[]
    # Fail-closed: if repo_mutating and CLP evidence is absent or failed,
    # AGL must surface the missing pre-PR gate evidence so AEX/PQX cannot
    # close out execution silently.
    if repo_mutating and clp_data is None:
        actions.append({
            "owner_system":"PRL",
            "action_type":"produce_clp_evidence",
            "reason_code":"clp_evidence_missing",
            "source_failure_ref":clp_evidence_artifact or "outputs/core_loop_pre_pr_gate/core_loop_pre_pr_gate_result.json",
            "recommended_artifact":"outputs/core_loop_pre_pr_gate/core_loop_pre_pr_gate_result.json",
        })
        compliance="B"+"LOCK"
    elif clp_data is not None and clp_data.get("gate_status")=="block":
        actions.append({
            "owner_system":"PRL",
            "action_type":"resolve_clp_block",
            "reason_code":(clp_data.get("failure_classes") or ["clp_gate_block"])[0],
            "source_failure_ref":clp_evidence_artifact or "outputs/core_loop_pre_pr_gate/core_loop_pre_pr_gate_result.json",
            "recommended_artifact":"outputs/core_loop_pre_pr_gate/core_loop_pre_pr_gate_result.json",
        })
        if repo_mutating:
            compliance="B"+"LOCK"
    # CLP-02: PR-ready guard evidence forces fail-closed semantics for AGL.
    # If a not_ready/human_review_required guard result is present, AGL must
    # report compliance BLOCK regardless of CLP evidence — the guard is the
    # canonical PR-ready signal that AEX/PQX/CDE/SEL consume downstream.
    if repo_mutating and agent_pr_ready_result_ref and pr_ready_data is None:
        actions.append({
            "owner_system":"CLP",
            "action_type":"rerun_agent_pr_ready_guard",
            "reason_code":"agent_pr_ready_evidence_invalid",
            "source_failure_ref":agent_pr_ready_result_ref,
            "recommended_artifact":"outputs/core_loop_pre_pr_gate/agent_pr_ready_result.json",
        })
        compliance="B"+"LOCK"
    elif pr_ready_data is not None:
        status=pr_ready_data.get("pr_ready_status")
        if status!="ready":
            reason=(pr_ready_data.get("reason_codes") or ["pre_pr_gate_blocked"])[0]
            actions.append({
                "owner_system":"PRL",
                "action_type":"resolve_pr_ready_block",
                "reason_code":reason if isinstance(reason,str) and reason else "pre_pr_gate_blocked",
                "source_failure_ref":agent_pr_ready_result_ref or "outputs/core_loop_pre_pr_gate/agent_pr_ready_result.json",
                "recommended_artifact":"outputs/core_loop_pre_pr_gate/agent_pr_ready_result.json",
            })
            if repo_mutating:
                compliance="B"+"LOCK"
    if compliance!="PASS":
        for leg in CORE:
            if legs[leg]["status"] in {"missing","partial","failed","unknown"}:
                actions.append({"owner_system":leg,"action_type":"add_eval_case" if leg=="EVL" else "add_repair_pattern","reason_code":legs[leg]["reason_codes"][0],"source_failure_ref":refs[0] if refs else "artifacts/unknown.json","recommended_artifact":f"artifacts/{leg.lower()}_evidence.json"})
                break
    return {"artifact_type":"agent_core_loop_run_record","schema_version":"1.0.0","work_item_id":work_item_id,"agent_type":agent_type if agent_type in {"codex","claude","other","unknown"} else "unknown","repo_mutating":repo_mutating,"source_refs":refs,"changed_surfaces":[],"loop_legs":legs,"overlays":overlays,"first_missing_leg":first_missing,"first_failed_leg":first_failed,"core_loop_complete":complete,"compliance_status":compliance,"learning_actions":actions,"trace_refs":[],"replay_refs":[],"authority_scope":"observation_only"}
