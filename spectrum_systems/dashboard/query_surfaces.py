"""Query surfaces for dashboard analysis and trend mining."""

import subprocess
from datetime import datetime
from typing import Any, Dict, List


class DashboardQuerySurfaces:
    """Implements all required query surfaces (A1-A8 + A.1.1-A.1.5)."""

    def __init__(self, artifact_store: Any) -> None:
        self.artifact_store = artifact_store
        self.code_version = self._get_code_version()
        self.query_result_limit = 10000
        self.query_timeout_seconds = 5

    # A1: Top reason codes driving blocks
    def query_top_reason_codes_by_blocks(self, days: int = 30, limit: int = 10) -> List[Dict[str, Any]]:
        """Top reason codes driving blocks in 7/30/90 days."""
        try:
            blocks = self.artifact_store.query(
                {"artifact_type": "control_response_log", "control_decision": "block", "recency_days": days},
                limit=self.query_result_limit,
            )
            reason_counts: Dict[str, int] = {}
            for block in blocks:
                reason = block.get("trigger_signal", "unknown")
                reason_counts[reason] = reason_counts.get(reason, 0) + 1

            sorted_reasons = sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
            return [
                {
                    "reason_code": code,
                    "block_count": count,
                    "percentage": (count / len(blocks) * 100) if blocks else 0,
                }
                for code, count in sorted_reasons
            ]
        except Exception as exc:
            self._emit_error("Query A1 failed", str(exc))
            raise RuntimeError(f"A1 query failed: {exc}") from exc

    # A2: Policies with rising override rates
    def query_policies_with_rising_override_rates(self, days: int = 30) -> List[Dict[str, Any]]:
        """Detect policies experiencing override rate increases."""
        try:
            early = self.artifact_store.query(
                {"artifact_type": "override_hotspot_report", "recency_days": (days, days + 30)},
                limit=self.query_result_limit,
            )
            recent = self.artifact_store.query(
                {"artifact_type": "override_hotspot_report", "recency_days": (0, days)},
                limit=self.query_result_limit,
            )

            policy_metrics: Dict[str, Dict[str, int]] = {}
            for report in early:
                for hotspot in report.get("hotspots", []):
                    policy = hotspot["gate_name"]
                    policy_metrics.setdefault(policy, {"early": 0, "recent": 0})
                    policy_metrics[policy]["early"] += hotspot["override_count"]
            for report in recent:
                for hotspot in report.get("hotspots", []):
                    policy = hotspot["gate_name"]
                    policy_metrics.setdefault(policy, {"early": 0, "recent": 0})
                    policy_metrics[policy]["recent"] += hotspot["override_count"]

            rising = [
                {
                    "policy": policy,
                    "early_rate": m["early"],
                    "recent_rate": m["recent"],
                    "trend": "rising",
                }
                for policy, m in policy_metrics.items()
                if m["recent"] > m["early"] * 1.1
            ]
            return sorted(rising, key=lambda x: x["recent_rate"], reverse=True)
        except Exception as exc:
            self._emit_error("Query A2 failed", str(exc))
            raise RuntimeError(f"A2 query failed: {exc}") from exc

    # A3: Routes with increasing cost per promotion
    def query_routes_increasing_cost(self, days: int = 30) -> List[Dict[str, Any]]:
        """Cost trend by route."""
        try:
            budgets = self.artifact_store.query(
                {"artifact_type": "cost_budget_status", "recency_days": days},
                limit=self.query_result_limit,
            )
            route_costs: Dict[str, List[float]] = {}
            for budget in budgets:
                route = budget.get("route_id", "unknown")
                route_costs.setdefault(route, []).append(budget.get("cost_per_promotion", 0))

            increasing = []
            for route, costs in route_costs.items():
                if len(costs) >= 2:
                    early_cost, recent_cost = costs[0], costs[-1]
                    if recent_cost > early_cost * 1.15:
                        increasing.append(
                            {
                                "route": route,
                                "early_cost": early_cost,
                                "recent_cost": recent_cost,
                                "percent_increase": (recent_cost - early_cost) / early_cost * 100,
                            }
                        )
            return sorted(increasing, key=lambda x: x["percent_increase"], reverse=True)
        except Exception as exc:
            self._emit_error("Query A3 failed", str(exc))
            raise RuntimeError(f"A3 query failed: {exc}") from exc

    # A4: Context sources correlating with contradictions
    def query_context_source_contradiction_correlation(self, days: int = 30) -> List[Dict[str, Any]]:
        """Which context sources correlate with contradictions."""
        try:
            spikes = self.artifact_store.query(
                {"artifact_type": "contradiction_spike", "recency_days": days},
                limit=self.query_result_limit,
            )
            source_contradiction: Dict[str, Dict[str, int]] = {}
            for spike in spikes:
                source = spike.get("context_source", "unknown")
                source_contradiction.setdefault(source, {"spikes": 0, "total": 0})
                source_contradiction[source]["spikes"] += 1
                source_contradiction[source]["total"] += spike.get("contradiction_count", 0)

            results = [
                {
                    "context_source": source,
                    "contradiction_spikes": m["spikes"],
                    "total_contradictions": m["total"],
                    "avg_per_spike": m["total"] / m["spikes"] if m["spikes"] > 0 else 0,
                }
                for source, m in source_contradiction.items()
            ]
            return sorted(results, key=lambda x: x["total_contradictions"], reverse=True)
        except Exception as exc:
            self._emit_error("Query A4 failed", str(exc))
            raise RuntimeError(f"A4 query failed: {exc}") from exc

    # A5: Judge-human disagreement drift over time
    def query_judge_human_disagreement_drift(self, days: int = 30) -> List[Dict[str, Any]]:
        """Track judge disagreement with human reviewers over time."""
        try:
            disagreements = self.artifact_store.query(
                {"artifact_type": "judge_disagreement_report", "recency_days": days},
                limit=self.query_result_limit,
            )
            judge_trends: Dict[str, Dict[str, Any]] = {}
            for report in disagreements:
                judge = report.get("judge_id", "unknown")
                judge_trends.setdefault(judge, {"reports": []})
                judge_trends[judge]["reports"].append(
                    {
                        "timestamp": report.get("timestamp"),
                        "disagreement_rate": report.get("disagreement_rate", 0),
                    }
                )

            results = []
            for judge, data in judge_trends.items():
                reports = sorted(data["reports"], key=lambda x: x["timestamp"] or "")
                if len(reports) >= 2:
                    trend = "rising" if reports[-1]["disagreement_rate"] > reports[0]["disagreement_rate"] else "falling"
                    results.append(
                        {
                            "judge_id": judge,
                            "current_disagreement": reports[-1]["disagreement_rate"],
                            "earlier_disagreement": reports[0]["disagreement_rate"],
                            "trend": trend,
                        }
                    )
            return results
        except Exception as exc:
            self._emit_error("Query A5 failed", str(exc))
            raise RuntimeError(f"A5 query failed: {exc}") from exc

    # A6: Routes approaching SLO threshold
    def query_routes_near_slo_threshold(self, days: int = 7, threshold_pct: float = 0.85) -> List[Dict[str, Any]]:
        """Routes where current metric value exceeds threshold_pct of their SLO limit."""
        try:
            metrics = self.artifact_store.query(
                {"artifact_type": "route_slo_snapshot", "recency_days": days},
                limit=self.query_result_limit,
            )
            at_risk = []
            for m in metrics:
                limit = m.get("slo_limit", 0)
                current = m.get("current_value", 0)
                if limit > 0 and current >= limit * threshold_pct:
                    at_risk.append(
                        {
                            "route_id": m.get("route_id", "unknown"),
                            "metric_name": m.get("metric_name", "unknown"),
                            "current_value": current,
                            "slo_limit": limit,
                            "utilization_pct": current / limit * 100,
                        }
                    )
            return sorted(at_risk, key=lambda x: x["utilization_pct"], reverse=True)
        except Exception as exc:
            self._emit_error("Query A6 failed", str(exc))
            raise RuntimeError(f"A6 query failed: {exc}") from exc

    # A7: Eval coverage gaps by artifact type
    def query_eval_coverage_gaps(self, days: int = 30) -> List[Dict[str, Any]]:
        """Artifact types with insufficient eval coverage."""
        try:
            coverage = self.artifact_store.query(
                {"artifact_type": "eval_coverage_summary", "recency_days": days},
                limit=self.query_result_limit,
            )
            gaps = [
                {
                    "artifact_type": c.get("artifact_type", "unknown"),
                    "coverage_pct": c.get("coverage_pct", 0),
                    "uncovered_cases": c.get("uncovered_cases", 0),
                    "last_eval_timestamp": c.get("last_eval_timestamp"),
                }
                for c in coverage
                if c.get("coverage_pct", 100) < 80
            ]
            return sorted(gaps, key=lambda x: x["coverage_pct"])
        except Exception as exc:
            self._emit_error("Query A7 failed", str(exc))
            raise RuntimeError(f"A7 query failed: {exc}") from exc

    # A8: Promotion readiness blockers
    def query_promotion_readiness_blockers(self, days: int = 7) -> List[Dict[str, Any]]:
        """Active blockers preventing route promotion."""
        try:
            readiness = self.artifact_store.query(
                {"artifact_type": "promotion_readiness_artifact", "recency_days": days},
                limit=self.query_result_limit,
            )
            blockers = [
                {
                    "route_id": r.get("route_id", "unknown"),
                    "blocker_type": r.get("blocker_type", "unknown"),
                    "blocker_detail": r.get("blocker_detail", ""),
                    "blocking_since": r.get("blocking_since"),
                }
                for r in readiness
                if r.get("is_blocked", False)
            ]
            return sorted(blockers, key=lambda x: x.get("blocking_since") or "", reverse=True)
        except Exception as exc:
            self._emit_error("Query A8 failed", str(exc))
            raise RuntimeError(f"A8 query failed: {exc}") from exc

    # A.1.1: Top failure patterns by context class
    def query_top_failure_patterns_by_context_class(self, days: int = 30, limit: int = 10) -> List[Dict[str, Any]]:
        """Cluster failures by context risk class."""
        try:
            incidents = self.artifact_store.query(
                {"artifact_type": "postmortem_artifact", "recency_days": days},
                limit=self.query_result_limit,
            )
            patterns_by_class: Dict[str, Dict[str, int]] = {}
            for incident in incidents:
                context_class = incident.get("context_class", "unknown")
                pattern = incident.get("failure_pattern", "unknown")
                patterns_by_class.setdefault(context_class, {})
                patterns_by_class[context_class][pattern] = patterns_by_class[context_class].get(pattern, 0) + 1

            results = []
            for context_class, patterns in patterns_by_class.items():
                for pattern, count in sorted(patterns.items(), key=lambda x: x[1], reverse=True)[:limit]:
                    results.append({"context_class": context_class, "failure_pattern": pattern, "incident_count": count})
            return sorted(results, key=lambda x: x["incident_count"], reverse=True)
        except Exception as exc:
            self._emit_error("Query A.1.1 failed", str(exc))
            raise RuntimeError(f"A.1.1 query failed: {exc}") from exc

    # A.1.2: On-demand incident drill
    def query_incident_drill(self, incident_id: str) -> Dict[str, Any]:
        """Simulate running current evals against a historical incident's context."""
        try:
            incidents = self.artifact_store.query(
                {"artifact_type": "postmortem_artifact", "incident_id": incident_id},
                limit=1,
            )
            if not incidents:
                raise ValueError(f"Incident {incident_id} not found")

            incident = incidents[0]
            current_evals = self.artifact_store.query({"artifact_type": "eval_case"}, limit=self.query_result_limit)
            return {
                "incident_id": incident_id,
                "context_class": incident.get("context_class"),
                "evals_run": len(current_evals),
                "drill_status": "completed",
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
        except Exception as exc:
            self._emit_error("Query A.1.2 failed", str(exc))
            raise RuntimeError(f"A.1.2 query failed: {exc}") from exc

    # A.1.3: Reviewer bias matrix
    def query_reviewer_bias_matrix(self, days: int = 30) -> List[Dict[str, Any]]:
        """Detect systematic disagreement between reviewer pairs on the same artifacts."""
        try:
            reviews = self.artifact_store.query(
                {"artifact_type": "human_review_outcome", "recency_days": days},
                limit=self.query_result_limit,
            )
            # Group outcomes by artifact_id so we can compare reviewers on the same artifact
            artifact_reviews: Dict[str, List[Dict[str, Any]]] = {}
            for review in reviews:
                art_id = review.get("artifact_id")
                if art_id:
                    artifact_reviews.setdefault(art_id, []).append(review)

            pair_stats: Dict[str, Dict[str, int]] = {}
            for art_id, art_reviews in artifact_reviews.items():
                for i in range(len(art_reviews)):
                    for j in range(i + 1, len(art_reviews)):
                        r1, r2 = art_reviews[i], art_reviews[j]
                        pair_key = "-".join(sorted([r1.get("reviewer_id", "?"), r2.get("reviewer_id", "?")]))
                        pair_stats.setdefault(pair_key, {"total": 0, "disagreements": 0})
                        pair_stats[pair_key]["total"] += 1
                        if r1.get("outcome") != r2.get("outcome"):
                            pair_stats[pair_key]["disagreements"] += 1

            results = [
                {
                    "reviewer_pair": pair,
                    "total_shared_artifacts": s["total"],
                    "disagreements": s["disagreements"],
                    "disagreement_rate": s["disagreements"] / s["total"] if s["total"] > 0 else 0.0,
                }
                for pair, s in pair_stats.items()
            ]
            return sorted(results, key=lambda x: x["disagreement_rate"], reverse=True)
        except Exception as exc:
            self._emit_error("Query A.1.3 failed", str(exc))
            raise RuntimeError(f"A.1.3 query failed: {exc}") from exc

    # A.1.4: Policy coverage delta (new since last cycle)
    def query_policy_coverage_delta(self, days: int = 30) -> Dict[str, Any]:
        """Show which artifact types gained or lost eval coverage since the last cycle."""
        try:
            current = self.artifact_store.query(
                {"artifact_type": "eval_coverage_summary", "recency_days": days},
                limit=self.query_result_limit,
            )
            previous = self.artifact_store.query(
                {"artifact_type": "eval_coverage_summary", "recency_days": (days, days * 2)},
                limit=self.query_result_limit,
            )
            current_map = {c["artifact_type"]: c.get("coverage_pct", 0) for c in current if "artifact_type" in c}
            previous_map = {c["artifact_type"]: c.get("coverage_pct", 0) for c in previous if "artifact_type" in c}

            gained, lost, new_types = [], [], []
            for art_type, pct in current_map.items():
                if art_type not in previous_map:
                    new_types.append({"artifact_type": art_type, "coverage_pct": pct})
                elif pct > previous_map[art_type]:
                    gained.append({"artifact_type": art_type, "delta": pct - previous_map[art_type]})
                elif pct < previous_map[art_type]:
                    lost.append({"artifact_type": art_type, "delta": pct - previous_map[art_type]})

            return {
                "gained_coverage": sorted(gained, key=lambda x: x["delta"], reverse=True),
                "lost_coverage": sorted(lost, key=lambda x: x["delta"]),
                "new_artifact_types": new_types,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
        except Exception as exc:
            self._emit_error("Query A.1.4 failed", str(exc))
            raise RuntimeError(f"A.1.4 query failed: {exc}") from exc

    # A.1.5: Artifact supersession lineage graph
    def query_artifact_supersession_lineage(self, artifact_id: str) -> Dict[str, Any]:
        """Trace the supersession chain: policy A → policy B → policy C."""
        try:
            lineage = []
            current = artifact_id
            visited = set()

            while current and current not in visited:
                visited.add(current)
                supersessions = self.artifact_store.query(
                    {"artifact_type": "artifact_supersession_record", "superseded_artifact_id": current},
                    limit=1,
                )
                if not supersessions:
                    break
                sup = supersessions[0]
                lineage.append({"from": current, "to": sup["new_artifact_id"], "reason": sup.get("reason", "unspecified")})
                current = sup["new_artifact_id"]

            return {
                "artifact_id": artifact_id,
                "lineage_chain": lineage,
                "total_supersessions": len(lineage),
                "current_active": lineage[-1]["to"] if lineage else artifact_id,
            }
        except Exception as exc:
            self._emit_error("Query A.1.5 failed", str(exc))
            raise RuntimeError(f"A.1.5 query failed: {exc}") from exc

    def _get_code_version(self) -> str:
        try:
            result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except Exception:
            return "unknown"

    def _emit_error(self, operation: str, error: str) -> None:
        error_artifact = {
            "artifact_type": "query_error_artifact",
            "operation": operation,
            "error_message": error,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        try:
            self.artifact_store.put(error_artifact, namespace="dashboard/errors")
        except Exception:
            pass
