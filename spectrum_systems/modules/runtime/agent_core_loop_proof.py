from __future__ import annotations
from pathlib import Path
import json

def evaluate_agl_repo_mutating_evidence(*, repo_mutating: bool, clp_result_path: str) -> dict:
    p=Path(clp_result_path)
    if repo_mutating and not p.is_file():
        return {"compliance_status":"HOLD","reason_codes":["missing_core_loop_pre_pr_gate_evidence"]}
    if p.is_file():
        d=json.loads(p.read_text(encoding='utf-8'))
        if d.get('authority_scope')!='observation_only':
            return {"compliance_status":"HOLD","reason_codes":["invalid_authority_scope_claim"]}
        if d.get('gate_status')=='blocked':
            return {"compliance_status":"HOLD","reason_codes":["core_loop_pre_pr_gate_blocked"]}
    return {"compliance_status":"PASS","reason_codes":[]}
