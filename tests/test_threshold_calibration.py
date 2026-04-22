"""Tests for threshold calibration surfaces (F1-F5).

These tests validate that miscalibration signals are correctly surfaced
and that threshold-crossing detection works across query surfaces.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from spectrum_systems.dashboard.query_surfaces import DashboardQuerySurfaces
from spectrum_systems.dashboard.artifact_intelligence_layer import ArtifactIntelligenceLayer


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


# F1: Rising override rate crosses 10% threshold
def test_f1_rising_override_crosses_threshold() -> None:
    from unittest.mock import MagicMock
    store = MagicMock()
    # early period has count 5; recent period has count 8 (8 > 5 * 1.1 = 5.5 → rising)
    store.query.side_effect = [
        [{"artifact_type": "override_hotspot_report", "hotspots": [{"gate_name": "gate-cal", "override_count": 5}]}],
        [{"artifact_type": "override_hotspot_report", "hotspots": [{"gate_name": "gate-cal", "override_count": 8}]}],
    ]
    store.put = MagicMock()
    qs = DashboardQuerySurfaces(store)
    results = qs.query_policies_with_rising_override_rates()
    assert any(r["policy"] == "gate-cal" for r in results)


# F2: Cost increase below 15% threshold not flagged
def test_f2_cost_below_threshold_not_flagged() -> None:
    store = MockArtifactStore([
        {"artifact_type": "cost_budget_status", "route_id": "r-ok", "cost_per_promotion": 100.0},
        {"artifact_type": "cost_budget_status", "route_id": "r-ok", "cost_per_promotion": 114.0},
    ])
    qs = DashboardQuerySurfaces(store)
    results = qs.query_routes_increasing_cost()
    assert all(r["route"] != "r-ok" for r in results)


# F3: Cost increase above 15% threshold is flagged
def test_f3_cost_above_threshold_flagged() -> None:
    store = MockArtifactStore([
        {"artifact_type": "cost_budget_status", "route_id": "r-high", "cost_per_promotion": 100.0},
        {"artifact_type": "cost_budget_status", "route_id": "r-high", "cost_per_promotion": 120.0},
    ])
    qs = DashboardQuerySurfaces(store)
    results = qs.query_routes_increasing_cost()
    assert any(r["route"] == "r-high" for r in results)
    flagged = next(r for r in results if r["route"] == "r-high")
    assert flagged["percent_increase"] == pytest.approx(20.0)


# F4: SLO at exactly threshold_pct is included
def test_f4_slo_at_boundary_included() -> None:
    store = MockArtifactStore([
        {"artifact_type": "route_slo_snapshot", "route_id": "r-boundary", "metric_name": "latency", "current_value": 850, "slo_limit": 1000},
    ])
    qs = DashboardQuerySurfaces(store)
    results = qs.query_routes_near_slo_threshold(threshold_pct=0.85)
    assert any(r["route_id"] == "r-boundary" for r in results)


# F5: Coverage exactly at 80% not returned as gap
def test_f5_coverage_at_threshold_not_a_gap() -> None:
    store = MockArtifactStore([
        {"artifact_type": "eval_coverage_summary", "artifact_type": "type-ok", "coverage_pct": 80, "uncovered_cases": 0},
    ])
    qs = DashboardQuerySurfaces(store)
    results = qs.query_eval_coverage_gaps()
    assert all(r.get("coverage_pct", 100) < 80 for r in results)
