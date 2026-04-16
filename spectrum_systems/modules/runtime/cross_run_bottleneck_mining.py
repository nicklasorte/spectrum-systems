from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, List
from spectrum_systems.modules.runtime.bne_utils import ensure_contract


def mine_cross_run_bottlenecks(*, trace_id: str, runs: List[Dict[str, any]]) -> Dict[str, Dict[str, any]]:
    reasons = Counter()
    overrides = Counter()
    for run in runs:
        for code in run.get("reason_codes", []):
            reasons[code]+=1
        overrides[run.get("policy_version", "unknown")]+=int(run.get("override_count",0))
    top = reasons.most_common(5)
    bottleneck = ensure_contract({"artifact_type":"cross_run_bottleneck_report","schema_version":"1.0.0","trace_id":trace_id,"outputs":{"top_reason_codes":top}}, "cross_run_bottleneck_report")
    route = ensure_contract({"artifact_type":"route_efficiency_report","schema_version":"1.0.0","trace_id":trace_id,"outputs":{"cost_per_promotion": round(sum(r.get('cost',1.0) for r in runs)/max(sum(r.get('promotions',0) for r in runs),1),3),"override_by_policy_version": dict(overrides)}}, "route_efficiency_report")
    hotspots = [k for k, v in reasons.items() if "evidence" in k and v > 0]
    ev_gap = ensure_contract(
        {
            "report_id": "EGH-ABCDEF123456",
            "schema_version": "1.0.0",
            "trace_id": trace_id if trace_id.startswith("trace-") else f"trace-{trace_id}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "hotspots": [{"artifact_family": h, "missing_stages": ["pre_merge"]} for h in hotspots] or [{"artifact_family": "none", "missing_stages": ["offline"]}],
        },
        "evidence_gap_hotspot_report",
    )
    return {"bottleneck": bottleneck, "route": route, "evidence_gap": ev_gap}
