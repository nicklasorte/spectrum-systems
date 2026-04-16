from __future__ import annotations
from typing import Dict
from spectrum_systems.modules.runtime.bne_utils import BNEBlockError, ensure_contract


def evaluate_policy_regression(*, trace_id: str, canary_block_rate: float, current_block_rate: float, threshold: float = 0.1) -> Dict[str, Dict[str, any]]:
    regression = canary_block_rate - current_block_rate
    unacceptable = regression > threshold
    report = ensure_contract({"artifact_type":"policy_regression_report","schema_version":"1.0.0","trace_id":trace_id,"outputs":{"regression":regression,"threshold":threshold,"unacceptable":unacceptable}}, "policy_regression_report")
    canary = ensure_contract({"artifact_type":"policy_canary_record","schema_version":"1.0.0","trace_id":trace_id,"outputs":{"candidate_block_rate":canary_block_rate,"current_block_rate":current_block_rate}}, "policy_canary_record")
    rollback = ensure_contract({"artifact_type":"policy_rollback_record","schema_version":"1.0.0","trace_id":trace_id,"outputs":{"required":unacceptable,"reason":"canary_regression" if unacceptable else "none"}}, "policy_rollback_record")
    if unacceptable:
        raise BNEBlockError("unacceptable canary regression")
    return {"report": report, "canary": canary, "rollback": rollback}
