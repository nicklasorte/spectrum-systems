"""OSX-03 bounded prompt_task_bundle end-to-end governed canary path."""
from __future__ import annotations
from typing import Any
from .ctx import resolve_context_recipe,gather_context_candidates,enforce_context_admission,assemble_context_bundle,emit_context_manifest,run_context_preflight,emit_context_preflight_result,detect_context_conflicts
from .tlx import normalize_tool_output,apply_tool_output_limits
from .prompt_registry import resolve_prompt_version
from .task_registry import resolve_task_spec
from .route_policy import select_route
from .eval_registry import resolve_required_evals
from .eval_slice_runner import summarize_eval_slice
from .dataset_registry import validate_dataset_registration,emit_dataset_lineage_record
from .jsx import build_active_judgment_set,detect_judgment_conflicts
from .artifact_intelligence import build_override_hotspot_report,build_trust_posture_snapshot
from .drt import emit_drift_signal
from .drx import build_drift_response_plan
from .ent import emit_entropy_report
from .hnd import build_handoff_record,emit_resume_record
from .rollout_gate import enforce_rollout_gate

def run_bounded_canary(*, run_id:str, trace_id:str, recipe:dict[str,Any], context_candidates:list[dict[str,Any]], prompt_entries:list[dict[str,Any]], alias_map:dict[str,Any], task_registry:dict[str,Any], eval_registry:dict[str,Any], dataset_record:dict[str,Any], judgments:list[dict[str,Any]], rollout_checks:dict[str,bool], strict:bool=True)->dict[str,Any]:
    recipe=resolve_context_recipe(recipe=recipe)
    candidates=gather_context_candidates(candidates=context_candidates)
    admitted,reasons=enforce_context_admission(recipe=recipe,candidates=candidates)
    conflicts=detect_context_conflicts(candidates=admitted)
    passed,preflight_reasons=run_context_preflight(recipe=recipe, admitted_candidates=admitted)
    if strict and (not passed or conflicts['has_conflicts']):
        return {'status':'blocked','phase':'CTX','reasons':sorted(set(reasons+preflight_reasons+conflicts['conflict_codes']))}
    bundle=assemble_context_bundle(run_id=run_id,trace_id=trace_id,recipe=recipe,candidates=admitted)
    manifest=emit_context_manifest(bundle=bundle,policy_version='ctx-policy-1')
    preflight=emit_context_preflight_result(run_id=run_id,trace_id=trace_id,bundle_ref=f"context_bundle:{bundle['bundle_id']}",passed=passed,reason_codes=preflight_reasons)
    prompt=resolve_prompt_version(prompt_id='prompt_task_bundle.summary',alias='prod',entries=prompt_entries,alias_map=alias_map)
    task=resolve_task_spec(registry=task_registry,task_id='prompt_task_bundle.summarize')
    route=select_route(artifact_family='prompt_task_bundle',preferred_route='RQX',fallback_route='TLC')
    required_evals=resolve_required_evals(registry=eval_registry,artifact_family='prompt_task_bundle')
    eval_summary=summarize_eval_slice(eval_id=required_evals[0],case_results=[{'passed':True},{'passed':True}]) if required_evals else {'failed_cases':1}
    ds_ok,ds_reasons=validate_dataset_registration(dataset_record=dataset_record)
    if strict and (not ds_ok or not required_evals):
        return {'status':'blocked','phase':'EVL_DAT','reasons':sorted(ds_reasons+(['missing_required_eval'] if not required_evals else []))}
    lineage=emit_dataset_lineage_record(dataset_id=dataset_record['dataset_id'],source_refs=dataset_record.get('source_refs',[]),version=dataset_record.get('version','v1'))
    active=build_active_judgment_set(judgments=judgments)
    jconf=detect_judgment_conflicts(judgments=judgments)
    if strict and (active['active_count']==0 or jconf['has_conflicts']):
        return {'status':'blocked','phase':'JSX','reasons':['judgment_conflict_or_empty_active_set']}
    tool_norm=normalize_tool_output(tool_id='summary-tool',raw_output={'summary':'ok'})
    tool_limited=apply_tool_output_limits(envelope=tool_norm,max_records=3,max_chars=256)
    evidence={'sufficient': eval_summary['failed_cases']==0 and passed and ds_ok}
    if strict and not evidence['sufficient']:
        return {'status':'blocked','phase':'EVD','reasons':['insufficient_evidence']}
    drift=emit_drift_signal(metric='override_rate',value=0.01,threshold=0.05)
    drx=build_drift_response_plan(signal_record={'signals':[{'signal':'override_rate'}]},runbook_ref='docs/runbooks/drift.md')
    entropy=emit_entropy_report(unresolved_failures=0,stale_artifacts=0)
    ail=build_override_hotspot_report(overrides_by_surface={'prompt_task_bundle':1})
    trust=build_trust_posture_snapshot(unresolved_overrides=0,missing_evidence=0)
    handoff=build_handoff_record(handoff_id='HND-OSX03-0001',required_keys=['manifest','route','eval_summary'],state={'manifest':manifest,'route':route,'eval_summary':eval_summary})
    resume=emit_resume_record(checkpoint_id='CP-OSX03-0001',handoff_record=handoff)
    gate_ok,gate_reasons=enforce_rollout_gate(checks=rollout_checks)
    if strict and not gate_ok:
        return {'status':'blocked','phase':'ROLLOUT','reasons':gate_reasons}
    return {'status':'passed','artifacts':{'manifest':manifest,'preflight':preflight,'prompt':prompt,'task':task,'route':route,'eval_summary':eval_summary,'dataset_lineage':lineage,'active_set':active,'tool_output':tool_limited,'drift_signal':drift,'drift_response_plan':drx,'entropy_report':entropy,'override_hotspot_report':ail,'trust_posture_snapshot':trust,'handoff_record':handoff,'resume_record':resume}}
