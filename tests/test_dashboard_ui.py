"""Tests for dashboard UI data contracts (E1-E8).

These tests verify that the data shapes returned by query surfaces match
what the dashboard UI layer expects (correct keys, types, sortability).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from spectrum_systems.dashboard.query_surfaces import DashboardQuerySurfaces


class MockArtifactStore:
    def __init__(self, data: Optional[List[Dict[str, Any]]] = None) -> None:
        self._data = data or []

    def query(self, filters: Dict[str, Any], limit: int = 10000) -> List[Dict[str, Any]]:
        results = []
        for item in self._data:
            match = True
            for key, value in filters.items():
                if key in ("recency_days",):
                    continue
                if isinstance(value, tuple):
                    continue
                if item.get(key) != value:
                    match = False
                    break
            if match:
                results.append(item)
        return results[:limit]

    def put(self, artifact: Dict[str, Any], namespace: str = "") -> None:
        pass


# E1: A1 result shape has required keys
def test_e1_a1_result_shape() -> None:
    store = MockArtifactStore([
        {"artifact_type": "control_response_log", "control_decision": "block", "trigger_signal": "drift"},
    ])
    qs = DashboardQuerySurfaces(store)
    results = qs.query_top_reason_codes_by_blocks()
    for row in results:
        assert "reason_code" in row
        assert "block_count" in row
        assert "percentage" in row
        assert isinstance(row["block_count"], int)
        assert isinstance(row["percentage"], float)


# E2: A3 result shape is numeric and sortable
def test_e2_a3_result_sortable() -> None:
    store = MockArtifactStore([
        {"artifact_type": "cost_budget_status", "route_id": "r-1", "cost_per_promotion": 100.0},
        {"artifact_type": "cost_budget_status", "route_id": "r-1", "cost_per_promotion": 150.0},
        {"artifact_type": "cost_budget_status", "route_id": "r-2", "cost_per_promotion": 50.0},
        {"artifact_type": "cost_budget_status", "route_id": "r-2", "cost_per_promotion": 75.0},
    ])
    qs = DashboardQuerySurfaces(store)
    results = qs.query_routes_increasing_cost()
    for row in results:
        assert "route" in row
        assert "percent_increase" in row
        assert isinstance(row["percent_increase"], float)
    percents = [r["percent_increase"] for r in results]
    assert percents == sorted(percents, reverse=True)


# E3: A5 result shape has trend field
def test_e3_a5_trend_field_present() -> None:
    store = MockArtifactStore([
        {"artifact_type": "judge_disagreement_report", "judge_id": "j-1", "disagreement_rate": 0.1, "timestamp": "2026-04-01T00:00:00Z"},
        {"artifact_type": "judge_disagreement_report", "judge_id": "j-1", "disagreement_rate": 0.2, "timestamp": "2026-04-20T00:00:00Z"},
    ])
    qs = DashboardQuerySurfaces(store)
    results = qs.query_judge_human_disagreement_drift()
    for row in results:
        assert "trend" in row
        assert row["trend"] in ("rising", "falling")


# E4: A.1.1 result has context_class and incident_count
def test_e4_a11_result_shape() -> None:
    store = MockArtifactStore([
        {"artifact_type": "postmortem_artifact", "context_class": "high-risk", "failure_pattern": "timeout"},
    ])
    qs = DashboardQuerySurfaces(store)
    results = qs.query_top_failure_patterns_by_context_class()
    for row in results:
        assert "context_class" in row
        assert "failure_pattern" in row
        assert "incident_count" in row
        assert isinstance(row["incident_count"], int)


# E5: A.1.5 lineage result has chain list
def test_e5_a15_lineage_chain_is_list() -> None:
    store = MockArtifactStore([
        {"artifact_type": "artifact_supersession_record", "superseded_artifact_id": "p-v1", "new_artifact_id": "p-v2", "reason": "fix"},
    ])
    qs = DashboardQuerySurfaces(store)
    result = qs.query_artifact_supersession_lineage("p-v1")
    assert isinstance(result["lineage_chain"], list)
    assert "from" in result["lineage_chain"][0]
    assert "to" in result["lineage_chain"][0]
    assert "reason" in result["lineage_chain"][0]


# E6: A.1.3 reviewer bias matrix has disagreement_rate as float 0-1
def test_e6_reviewer_bias_rate_in_range() -> None:
    store = MockArtifactStore([
        {"artifact_type": "human_review_outcome", "artifact_id": "a1", "reviewer_id": "r1", "outcome": "approve"},
        {"artifact_type": "human_review_outcome", "artifact_id": "a1", "reviewer_id": "r2", "outcome": "reject"},
    ])
    qs = DashboardQuerySurfaces(store)
    results = qs.query_reviewer_bias_matrix()
    for row in results:
        assert 0.0 <= row["disagreement_rate"] <= 1.0


# E7: A6 result has utilization_pct field
def test_e7_a6_result_has_utilization_pct() -> None:
    store = MockArtifactStore([
        {"artifact_type": "route_slo_snapshot", "route_id": "r-hot", "metric_name": "latency", "current_value": 950, "slo_limit": 1000},
    ])
    qs = DashboardQuerySurfaces(store)
    results = qs.query_routes_near_slo_threshold()
    for row in results:
        assert "utilization_pct" in row
        assert row["utilization_pct"] > 0


# E8: A8 result has blocker_type field
def test_e8_a8_result_has_blocker_type() -> None:
    store = MockArtifactStore([
        {"artifact_type": "promotion_readiness_artifact", "route_id": "r-b", "is_blocked": True, "blocker_type": "missing_cert", "blocker_detail": "no cert"},
    ])
    qs = DashboardQuerySurfaces(store)
    results = qs.query_promotion_readiness_blockers()
    for row in results:
        assert "blocker_type" in row
