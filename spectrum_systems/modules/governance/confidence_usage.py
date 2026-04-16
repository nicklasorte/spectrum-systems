from __future__ import annotations
from typing import Dict
from spectrum_systems.modules.runtime.bne_utils import BNEBlockError, ensure_contract


def enforce_confidence_usage(*, trace_id: str, confidence: float, has_required_eval: bool, policy_support: bool) -> Dict[str, Dict[str, any]]:
    policy = ensure_contract({"artifact_type":"confidence_usage_policy","schema_version":"1.0.0","trace_id":trace_id,"outputs":{"requires_eval":True,"requires_policy_support":True}}, "confidence_usage_policy")
    misuse = confidence > 0.8 and (not has_required_eval or not policy_support)
    violation = ensure_contract({"artifact_type":"confidence_violation_record","schema_version":"1.0.0","trace_id":trace_id,"outputs":{"misuse":misuse,"confidence":confidence}}, "confidence_violation_record")
    if misuse:
        raise BNEBlockError("confidence misuse")
    return {"policy": policy, "violation": violation}
