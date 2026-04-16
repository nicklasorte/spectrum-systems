from __future__ import annotations
from typing import Dict
from spectrum_systems.modules.runtime.bne_utils import BNEBlockError, ensure_contract

ALLOWED={"ACTIVE":{"HIBERNATE","COMPLETE"},"HIBERNATED":{"WAKE"},"WAKE":{"ACTIVE"},"COMPLETE":set()}

def evaluate_checkpoint_transition(*, trace_id: str, current_state: str, action: str) -> Dict[str, Dict[str, any]]:
    if action not in ALLOWED.get(current_state, set()):
        raise BNEBlockError("illegal wake/hibernate/state transition")
    stage = ensure_contract({"artifact_type":"checkpoint_stage_contract_record","schema_version":"1.0.0","trace_id":trace_id,"outputs":{"current_state":current_state,"action":action}}, "checkpoint_stage_contract_record")
    h = ensure_contract({"artifact_type":"checkpoint_hibernate_record","schema_version":"1.0.0","trace_id":trace_id,"outputs":{"entered": action=="HIBERNATE"}}, "checkpoint_hibernate_record")
    w = ensure_contract({"artifact_type":"checkpoint_wake_record","schema_version":"1.0.0","trace_id":trace_id,"outputs":{"entered": action=="WAKE"}}, "checkpoint_wake_record")
    return {"stage":stage,"hibernate":h,"wake":w}
