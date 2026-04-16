from __future__ import annotations
from typing import Dict
from spectrum_systems.modules.runtime.bne_utils import BNEBlockError, ensure_contract


def compute_bottleneck_alerts(*, trace_id: str, severe_drift: bool, repeated_blocks: int, evidence_gap_spike: bool, override_spike: bool) -> Dict[str, any]:
    alerts = []
    if severe_drift:
        alerts.append("severe_drift")
    if repeated_blocks >= 3:
        alerts.append("repeated_promotion_blocks")
    if evidence_gap_spike:
        alerts.append("evidence_gap_spike")
    if override_spike:
        alerts.append("override_spike")
    result = ensure_contract({"artifact_type":"bottleneck_alert_trigger_result","schema_version":"1.0.0","trace_id":trace_id,"outputs":{"alerts":alerts}}, "bottleneck_alert_trigger_result")
    if result["outputs"].get("alerts") is None:
        raise BNEBlockError("invalid alert computation")
    return result
