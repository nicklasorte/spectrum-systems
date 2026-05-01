import json
from pathlib import Path
from spectrum_systems.contracts import validate_artifact
from spectrum_systems.modules.runtime.agent_pr_update_policy import evaluate, load_policy

ROOT=Path(__file__).resolve().parents[1]

def test_example_validates():
    ex=json.loads((ROOT/'contracts/examples/agent_pr_update_ready_result.example.json').read_text())
    validate_artifact(ex,'agent_pr_update_ready_result')

def test_repo_mutating_unknown_not_ready():
    pol=load_policy(ROOT/'docs/governance/agent_pr_update_policy.json')
    out=evaluate(pol,None,None,None)
    assert out['readiness_status']=='not_ready'

def test_missing_clp_not_ready_when_repo_mutating():
    pol=load_policy(ROOT/'docs/governance/agent_pr_update_policy.json')
    out=evaluate(pol,None,{},True)
    assert 'clp_evidence_missing' in out['reason_codes']

def test_clp_block_not_ready():
    pol=load_policy(ROOT/'docs/governance/agent_pr_update_policy.json')
    clp={'gate_status':'block','checks':[]}
    out=evaluate(pol,clp,{},True)
    assert out['readiness_status']=='not_ready'

def test_warn_allowed_only_policy_codes():
    pol=load_policy(ROOT/'docs/governance/agent_pr_update_policy.json')
    clp={'gate_status':'warn','checks':[{'check_name':'authority_shape_preflight'},{'check_name':'authority_leak_guard'},{'check_name':'contract_enforcement'},{'check_name':'tls_generated_artifact_freshness','status':'warn','reason_codes':['tls_artifacts_updated']},{'check_name':'contract_preflight'},{'check_name':'selected_tests'}]}
    out=evaluate(pol,clp,{},True)
    assert 'clp_warn_reason_code_not_allowed' not in out['reason_codes']
