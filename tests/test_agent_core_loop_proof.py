import json
from spectrum_systems.modules.runtime.agent_core_loop_proof import evaluate_agl_repo_mutating_evidence

def test_pass_when_gate_pass(tmp_path):
 p=tmp_path/'g.json'; p.write_text(json.dumps({"gate_status":"pass","authority_scope":"observation_only"}))
 assert evaluate_agl_repo_mutating_evidence(repo_mutating=True, clp_result_path=str(p))["compliance_status"]=="PASS"
