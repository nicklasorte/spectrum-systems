"""Artifact intelligence layer: high-cardinality query indexes (C1-C10)."""

from datetime import datetime
from typing import Any, Dict, List, Optional


class ArtifactIntelligenceLayer:
    """Builds and queries 10 pre-computed indexes for dashboard query acceleration."""

    def __init__(self, artifact_store: Any) -> None:
        self.artifact_store = artifact_store
        self._indexes: Dict[str, Any] = {}

    # C1: Route-to-block-count index
    def build_route_block_count_index(self, days: int = 30) -> Dict[str, int]:
        """Map route_id → block event count over the given window."""
        logs = self.artifact_store.query(
            {"artifact_type": "control_response_log", "control_decision": "block", "recency_days": days},
            limit=10000,
        )
        index: Dict[str, int] = {}
        for log in logs:
            route = log.get("route_id", "unknown")
            index[route] = index.get(route, 0) + 1
        self._indexes["C1_route_block_count"] = index
        return index

    def get_route_block_count(self, route_id: str) -> int:
        """O(1) lookup for a route's block count."""
        return self._indexes.get("C1_route_block_count", {}).get(route_id, 0)

    # C2: Policy-to-override-count index
    def build_policy_override_count_index(self, days: int = 30) -> Dict[str, int]:
        """Map policy/gate name → total override count."""
        reports = self.artifact_store.query(
            {"artifact_type": "override_hotspot_report", "recency_days": days},
            limit=10000,
        )
        index: Dict[str, int] = {}
        for report in reports:
            for hotspot in report.get("hotspots", []):
                policy = hotspot.get("gate_name", "unknown")
                index[policy] = index.get(policy, 0) + hotspot.get("override_count", 0)
        self._indexes["C2_policy_override_count"] = index
        return index

    def get_policy_override_count(self, policy_name: str) -> int:
        return self._indexes.get("C2_policy_override_count", {}).get(policy_name, 0)

    # C3: Context-source-to-contradiction index
    def build_context_source_contradiction_index(self, days: int = 30) -> Dict[str, int]:
        """Map context_source → total contradiction count."""
        spikes = self.artifact_store.query(
            {"artifact_type": "contradiction_spike", "recency_days": days},
            limit=10000,
        )
        index: Dict[str, int] = {}
        for spike in spikes:
            source = spike.get("context_source", "unknown")
            index[source] = index.get(source, 0) + spike.get("contradiction_count", 0)
        self._indexes["C3_context_source_contradiction"] = index
        return index

    def get_context_source_contradiction_count(self, source: str) -> int:
        return self._indexes.get("C3_context_source_contradiction", {}).get(source, 0)

    # C4: Judge-to-disagreement-rate index
    def build_judge_disagreement_rate_index(self, days: int = 30) -> Dict[str, float]:
        """Map judge_id → latest disagreement_rate."""
        reports = self.artifact_store.query(
            {"artifact_type": "judge_disagreement_report", "recency_days": days},
            limit=10000,
        )
        index: Dict[str, float] = {}
        for report in reports:
            judge = report.get("judge_id", "unknown")
            index[judge] = report.get("disagreement_rate", 0.0)
        self._indexes["C4_judge_disagreement_rate"] = index
        return index

    def get_judge_disagreement_rate(self, judge_id: str) -> float:
        return self._indexes.get("C4_judge_disagreement_rate", {}).get(judge_id, 0.0)

    # C5: Artifact-type-to-failure-count index
    def build_artifact_type_failure_count_index(self, days: int = 30) -> Dict[str, int]:
        """Map artifact_type → failure/incident count from postmortems."""
        incidents = self.artifact_store.query(
            {"artifact_type": "postmortem_artifact", "recency_days": days},
            limit=10000,
        )
        index: Dict[str, int] = {}
        for incident in incidents:
            art_type = incident.get("primary_artifact_type", "unknown")
            index[art_type] = index.get(art_type, 0) + 1
        self._indexes["C5_artifact_type_failure_count"] = index
        return index

    def get_artifact_type_failure_count(self, artifact_type: str) -> int:
        return self._indexes.get("C5_artifact_type_failure_count", {}).get(artifact_type, 0)

    # C6: Route-to-cost-trend index
    def build_route_cost_trend_index(self, days: int = 30) -> Dict[str, Dict[str, float]]:
        """Map route_id → {early_cost, recent_cost, trend_pct}."""
        budgets = self.artifact_store.query(
            {"artifact_type": "cost_budget_status", "recency_days": days},
            limit=10000,
        )
        route_costs: Dict[str, List[float]] = {}
        for budget in budgets:
            route = budget.get("route_id", "unknown")
            route_costs.setdefault(route, []).append(budget.get("cost_per_promotion", 0.0))

        index: Dict[str, Dict[str, float]] = {}
        for route, costs in route_costs.items():
            if len(costs) >= 2:
                early, recent = costs[0], costs[-1]
                index[route] = {
                    "early_cost": early,
                    "recent_cost": recent,
                    "trend_pct": (recent - early) / early * 100 if early > 0 else 0.0,
                }
        self._indexes["C6_route_cost_trend"] = index
        return index

    def get_route_cost_trend(self, route_id: str) -> Optional[Dict[str, float]]:
        return self._indexes.get("C6_route_cost_trend", {}).get(route_id)

    # C7: Incident-to-context-class index
    def build_incident_context_class_index(self, days: int = 30) -> Dict[str, str]:
        """Map incident_id → context_class."""
        incidents = self.artifact_store.query(
            {"artifact_type": "postmortem_artifact", "recency_days": days},
            limit=10000,
        )
        index: Dict[str, str] = {}
        for incident in incidents:
            inc_id = incident.get("incident_id", "")
            ctx_class = incident.get("context_class", "unknown")
            if inc_id:
                index[inc_id] = ctx_class
        self._indexes["C7_incident_context_class"] = index
        return index

    def get_incident_context_class(self, incident_id: str) -> str:
        return self._indexes.get("C7_incident_context_class", {}).get(incident_id, "unknown")

    # C8: Reviewer-to-disagreement-count index
    def build_reviewer_disagreement_count_index(self, days: int = 30) -> Dict[str, int]:
        """Map reviewer_id → total disagreement count across all paired reviews."""
        reviews = self.artifact_store.query(
            {"artifact_type": "human_review_outcome", "recency_days": days},
            limit=10000,
        )
        artifact_reviews: Dict[str, List[Dict[str, Any]]] = {}
        for review in reviews:
            art_id = review.get("artifact_id")
            if art_id:
                artifact_reviews.setdefault(art_id, []).append(review)

        index: Dict[str, int] = {}
        for art_reviews in artifact_reviews.values():
            outcomes = {r.get("reviewer_id"): r.get("outcome") for r in art_reviews}
            unique_outcomes = set(outcomes.values())
            if len(unique_outcomes) > 1:
                for reviewer_id in outcomes:
                    if reviewer_id:
                        index[reviewer_id] = index.get(reviewer_id, 0) + 1
        self._indexes["C8_reviewer_disagreement_count"] = index
        return index

    def get_reviewer_disagreement_count(self, reviewer_id: str) -> int:
        return self._indexes.get("C8_reviewer_disagreement_count", {}).get(reviewer_id, 0)

    # C9: Artifact-to-supersession-chain length index
    def build_artifact_supersession_chain_index(self, days: int = 90) -> Dict[str, int]:
        """Map originating artifact_id → length of its supersession chain."""
        records = self.artifact_store.query(
            {"artifact_type": "artifact_supersession_record", "recency_days": days},
            limit=10000,
        )
        successors: Dict[str, str] = {r["superseded_artifact_id"]: r["new_artifact_id"] for r in records if "superseded_artifact_id" in r and "new_artifact_id" in r}
        roots = set(successors.keys()) - set(successors.values())

        index: Dict[str, int] = {}
        for root in roots:
            depth = 0
            current = root
            visited = set()
            while current in successors and current not in visited:
                visited.add(current)
                current = successors[current]
                depth += 1
            index[root] = depth
        self._indexes["C9_artifact_supersession_chain"] = index
        return index

    def get_supersession_chain_length(self, artifact_id: str) -> int:
        return self._indexes.get("C9_artifact_supersession_chain", {}).get(artifact_id, 0)

    # C10: Control-decision-to-effectiveness index
    def build_control_decision_effectiveness_index(self, days: int = 30) -> Dict[str, Dict[str, Any]]:
        """Map control_decision type → {total, reversed, fpr}."""
        logs = self.artifact_store.query(
            {"artifact_type": "control_response_log", "recency_days": days},
            limit=10000,
        )
        index: Dict[str, Dict[str, Any]] = {}
        for log in logs:
            decision = log.get("control_decision", "unknown")
            index.setdefault(decision, {"total": 0, "reversed": 0})
            index[decision]["total"] += 1
            if log.get("status") == "reversed":
                index[decision]["reversed"] += 1

        for decision, stats in index.items():
            total = stats["total"]
            stats["false_positive_rate"] = stats["reversed"] / total if total > 0 else 0.0

        self._indexes["C10_control_decision_effectiveness"] = index
        return index

    def get_control_decision_effectiveness(self, decision: str) -> Optional[Dict[str, Any]]:
        return self._indexes.get("C10_control_decision_effectiveness", {}).get(decision)

    def build_all_indexes(self, days: int = 30) -> Dict[str, str]:
        """Build all indexes and return a status map."""
        builders = [
            ("C1", self.build_route_block_count_index),
            ("C2", self.build_policy_override_count_index),
            ("C3", self.build_context_source_contradiction_index),
            ("C4", self.build_judge_disagreement_rate_index),
            ("C5", self.build_artifact_type_failure_count_index),
            ("C6", self.build_route_cost_trend_index),
            ("C7", self.build_incident_context_class_index),
            ("C8", self.build_reviewer_disagreement_count_index),
            ("C9", lambda: self.build_artifact_supersession_chain_index(days=90)),
            ("C10", self.build_control_decision_effectiveness_index),
        ]
        status: Dict[str, str] = {}
        for name, builder in builders:
            try:
                builder()
                status[name] = "built"
            except Exception as exc:
                status[name] = f"failed: {exc}"
        return status
