"""Supporting governance signals for OSX-03 bounded rollout."""
from __future__ import annotations

def dependency_integrity(*, deps:dict[str,bool])->dict:
    bad=sorted([k for k,v in deps.items() if not v])
    return {'ok':not bad,'failed_dependencies':bad}

def cross_artifact_consistency(*, refs:dict[str,str])->dict:
    vals=set(refs.values())
    return {'consistent':len(vals)<=1,'refs':refs}

def normalize_external_input(*, payload:dict)->dict:
    return {str(k).lower(): payload[k] for k in sorted(payload.keys(), key=lambda x:str(x).lower())}

def compare_runs(*, baseline:dict, candidate:dict)->dict:
    changed=sorted([k for k in set(baseline)|set(candidate) if baseline.get(k)!=candidate.get(k)])
    return {'artifact_type':'comparison_result_record','changed_keys':changed,'changed_count':len(changed)}

def classify_risk(*, severity:str, likelihood:str)->dict:
    high = severity in {'high','critical'} or likelihood=='high'
    return {'artifact_type':'risk_classification_record','risk':'high' if high else 'normal'}

def synthesize_signals(*, signals:list[dict])->dict:
    return {'artifact_type':'signal_synthesis_summary','signal_count':len(signals),'signals':signals}
