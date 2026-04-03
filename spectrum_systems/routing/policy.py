from __future__ import annotations

from typing import Any, Dict, List


class RoutingDecisionError(RuntimeError):
    """Raised when a deterministic routing decision cannot be produced."""


def select_route(policy: Dict[str, Any], candidate_set: Dict[str, Any], *, trace_id: str, run_id: str) -> Dict[str, Any]:
    candidates = [
        c for c in candidate_set.get("candidates", [])
        if c["estimated_cost"] <= policy["selection_constraints"]["max_cost_usd"]
        and c["estimated_latency_ms"] <= policy["selection_constraints"]["max_latency_ms"]
    ]
    if not candidates:
        raise RoutingDecisionError("no routing candidate satisfies policy constraints")

    selected = sorted(candidates, key=lambda c: (c["estimated_cost"], c["estimated_latency_ms"], c["route_key"]))[0]
    return {
        "artifact_type": "routing_decision_record",
        "schema_version": "1.0.0",
        "decision_id": "rdr-" + f"{abs(hash((policy['policy_id'], selected['route_key'], selected['model_id']))) & ((1<<64)-1):016x}",
        "policy_id": policy["policy_id"],
        "policy_version": policy["policy_version"],
        "selected_route": {"route_key": selected["route_key"], "model_id": selected["model_id"]},
        "trace": {"trace_id": trace_id, "run_id": run_id},
    }
