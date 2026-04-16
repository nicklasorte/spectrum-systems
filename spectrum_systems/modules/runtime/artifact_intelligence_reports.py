from __future__ import annotations
from datetime import datetime, timezone
from typing import Dict
from spectrum_systems.modules.runtime.bne_utils import ensure_contract


def derive_intelligence_reports(*, trace_id: str, indexed: Dict[str, any]) -> Dict[str, Dict[str, any]]:
    rows = indexed.get("outputs", {}).get("rows", [])
    blocked = sum(1 for r in rows if r.get("control_decision") == "BLOCK")
    total = max(len(rows), 1)
    now = datetime.now(timezone.utc).isoformat()
    trace = trace_id if trace_id.startswith("trace-") else f"trace-{trace_id}"
    trust_score = round(1 - blocked / total, 3)
    health = ensure_contract(
        {
            "report_id": "AFH-ABCDEF123456",
            "schema_version": "1.0.0",
            "artifact_family": "wpg",
            "health_state": "critical" if blocked else "healthy",
            "reason_codes": ["blocked_artifacts"] if blocked else ["healthy"],
            "created_at": now,
            "trace_id": trace,
        },
        "artifact_family_health_report",
    )
    trust = ensure_contract(
        {
            "snapshot_id": "TPS-ABCDEF123456",
            "schema_version": "1.1.0",
            "overall_trust_state": "degraded" if blocked else "healthy",
            "eval_pass_rate": trust_score,
            "drift_status": "warning" if blocked else "stable",
            "replay_consistency": "consistent",
            "override_rate": 0.0,
            "readiness_state": "constrained" if blocked else "autonomous",
            "created_at": now,
            "trace_id": trace,
            "monitoring_contract_ref": "operations_monitoring_contract:OMC-ABCDEF123456",
            "operational_severity": "warning" if blocked else "normal",
            "operational_required_action": "investigate" if blocked else "none",
            "operational_escalation_state": "watch" if blocked else "none",
        },
        "trust_posture_snapshot",
    )
    trend = ensure_contract({"artifact_type": "trend_report_artifact", "schema_version": "1.0.0", "trace_id": trace_id, "outputs": {"delta_block_rate": blocked/total}}, "trend_report_artifact")
    rec = ensure_contract({"artifact_type": "improvement_recommendation_record", "schema_version": "1.0.0", "trace_id": trace_id, "outputs": {"recommendations": ["reduce recurring block reason codes"] if blocked else []}}, "improvement_recommendation_record")
    return {"health": health, "trust": trust, "trend": trend, "recommendation": rec, "trust_score": trust_score}
