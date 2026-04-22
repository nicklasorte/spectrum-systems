"""Tests for DashboardQuerySurfaces (A1-A8 + A.1.1-A.1.5)."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from spectrum_systems.dashboard.query_surfaces import DashboardQuerySurfaces


# ---------------------------------------------------------------------------
# Mock artifact store
# ---------------------------------------------------------------------------

class MockArtifactStore:
    def __init__(self, data: Optional[List[Dict[str, Any]]] = None) -> None:
        self._data = data or []
        self._written: List[Dict[str, Any]] = []

    def query(self, filters: Dict[str, Any], limit: int = 10000) -> List[Dict[str, Any]]:
        results = []
        for item in self._data:
            match = True
            for key, value in filters.items():
                if key == "recency_days":
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
        self._written.append(artifact)


def _ts(offset_days: int = 0) -> str:
    dt = datetime.utcnow() - timedelta(days=offset_days)
    return dt.isoformat() + "Z"


# ---------------------------------------------------------------------------
# A1: top reason codes by blocks
# ---------------------------------------------------------------------------

def test_a1_returns_sorted_reason_codes() -> None:
    store = MockArtifactStore([
        {"artifact_type": "control_response_log", "control_decision": "block", "trigger_signal": "drift", "timestamp": _ts()},
        {"artifact_type": "control_response_log", "control_decision": "block", "trigger_signal": "drift", "timestamp": _ts()},
        {"artifact_type": "control_response_log", "control_decision": "block", "trigger_signal": "timeout", "timestamp": _ts()},
    ])
    qs = DashboardQuerySurfaces(store)
    results = qs.query_top_reason_codes_by_blocks(days=30, limit=5)
    assert results[0]["reason_code"] == "drift"
    assert results[0]["block_count"] == 2


def test_a1_empty_store_returns_empty() -> None:
    qs = DashboardQuerySurfaces(MockArtifactStore([]))
    assert qs.query_top_reason_codes_by_blocks() == []


def test_a1_respects_limit() -> None:
    logs = [
        {"artifact_type": "control_response_log", "control_decision": "block", "trigger_signal": f"sig-{i}", "timestamp": _ts()}
        for i in range(20)
    ]
    qs = DashboardQuerySurfaces(MockArtifactStore(logs))
    results = qs.query_top_reason_codes_by_blocks(limit=3)
    assert len(results) <= 3


def test_a1_percentages_sum_to_100() -> None:
    store = MockArtifactStore([
        {"artifact_type": "control_response_log", "control_decision": "block", "trigger_signal": "a", "timestamp": _ts()},
        {"artifact_type": "control_response_log", "control_decision": "block", "trigger_signal": "b", "timestamp": _ts()},
    ])
    qs = DashboardQuerySurfaces(store)
    results = qs.query_top_reason_codes_by_blocks()
    total_pct = sum(r["percentage"] for r in results)
    assert abs(total_pct - 100.0) < 0.01


def test_a1_raises_on_store_error() -> None:
    store = MagicMock()
    store.query.side_effect = RuntimeError("db down")
    store.put = MagicMock()
    qs = DashboardQuerySurfaces(store)
    with pytest.raises(RuntimeError, match="A1 query failed"):
        qs.query_top_reason_codes_by_blocks()


# ---------------------------------------------------------------------------
# A2: policies with rising override rates
# ---------------------------------------------------------------------------

def test_a2_detects_rising_policy() -> None:
    from unittest.mock import MagicMock
    store = MagicMock()
    store.query.side_effect = [
        [{"artifact_type": "override_hotspot_report", "hotspots": [{"gate_name": "gate-A", "override_count": 5}]}],
        [{"artifact_type": "override_hotspot_report", "hotspots": [{"gate_name": "gate-A", "override_count": 10}]}],
    ]
    store.put = MagicMock()
    qs = DashboardQuerySurfaces(store)
    results = qs.query_policies_with_rising_override_rates(days=30)
    assert any(r["policy"] == "gate-A" for r in results)


def test_a2_stable_policy_not_returned() -> None:
    from unittest.mock import MagicMock
    store = MagicMock()
    store.query.side_effect = [
        [{"artifact_type": "override_hotspot_report", "hotspots": [{"gate_name": "gate-stable", "override_count": 5}]}],
        [{"artifact_type": "override_hotspot_report", "hotspots": [{"gate_name": "gate-stable", "override_count": 5}]}],
    ]
    store.put = MagicMock()
    qs = DashboardQuerySurfaces(store)
    results = qs.query_policies_with_rising_override_rates(days=30)
    assert all(r["policy"] != "gate-stable" for r in results)


# ---------------------------------------------------------------------------
# A3: routes with increasing cost
# ---------------------------------------------------------------------------

def test_a3_detects_increasing_cost() -> None:
    store = MockArtifactStore([
        {"artifact_type": "cost_budget_status", "route_id": "route-1", "cost_per_promotion": 100.0},
        {"artifact_type": "cost_budget_status", "route_id": "route-1", "cost_per_promotion": 120.0},
    ])
    qs = DashboardQuerySurfaces(store)
    results = qs.query_routes_increasing_cost(days=30)
    assert any(r["route"] == "route-1" for r in results)


def test_a3_stable_cost_not_returned() -> None:
    store = MockArtifactStore([
        {"artifact_type": "cost_budget_status", "route_id": "r-flat", "cost_per_promotion": 100.0},
        {"artifact_type": "cost_budget_status", "route_id": "r-flat", "cost_per_promotion": 101.0},
    ])
    qs = DashboardQuerySurfaces(store)
    results = qs.query_routes_increasing_cost()
    assert all(r["route"] != "r-flat" for r in results)


# ---------------------------------------------------------------------------
# A4: context source contradiction correlation
# ---------------------------------------------------------------------------

def test_a4_groups_by_source() -> None:
    store = MockArtifactStore([
        {"artifact_type": "contradiction_spike", "context_source": "src-A", "contradiction_count": 5},
        {"artifact_type": "contradiction_spike", "context_source": "src-A", "contradiction_count": 3},
        {"artifact_type": "contradiction_spike", "context_source": "src-B", "contradiction_count": 2},
    ])
    qs = DashboardQuerySurfaces(store)
    results = qs.query_context_source_contradiction_correlation()
    src_a = next(r for r in results if r["context_source"] == "src-A")
    assert src_a["total_contradictions"] == 8
    assert results[0]["context_source"] == "src-A"


# ---------------------------------------------------------------------------
# A5: judge-human disagreement drift
# ---------------------------------------------------------------------------

def test_a5_detects_rising_trend() -> None:
    store = MockArtifactStore([
        {"artifact_type": "judge_disagreement_report", "judge_id": "j-1", "disagreement_rate": 0.1, "timestamp": _ts(10)},
        {"artifact_type": "judge_disagreement_report", "judge_id": "j-1", "disagreement_rate": 0.3, "timestamp": _ts(1)},
    ])
    qs = DashboardQuerySurfaces(store)
    results = qs.query_judge_human_disagreement_drift()
    j1 = next(r for r in results if r["judge_id"] == "j-1")
    assert j1["trend"] == "rising"


def test_a5_single_report_not_included() -> None:
    store = MockArtifactStore([
        {"artifact_type": "judge_disagreement_report", "judge_id": "j-lone", "disagreement_rate": 0.2, "timestamp": _ts(1)},
    ])
    qs = DashboardQuerySurfaces(store)
    results = qs.query_judge_human_disagreement_drift()
    assert all(r["judge_id"] != "j-lone" for r in results)


# ---------------------------------------------------------------------------
# A6: routes near SLO threshold
# ---------------------------------------------------------------------------

def test_a6_detects_near_slo_route() -> None:
    store = MockArtifactStore([
        {"artifact_type": "route_slo_snapshot", "route_id": "r-hot", "metric_name": "latency_p99", "current_value": 900, "slo_limit": 1000},
    ])
    qs = DashboardQuerySurfaces(store)
    results = qs.query_routes_near_slo_threshold(threshold_pct=0.85)
    assert any(r["route_id"] == "r-hot" for r in results)


def test_a6_safe_route_excluded() -> None:
    store = MockArtifactStore([
        {"artifact_type": "route_slo_snapshot", "route_id": "r-safe", "metric_name": "latency_p99", "current_value": 100, "slo_limit": 1000},
    ])
    qs = DashboardQuerySurfaces(store)
    results = qs.query_routes_near_slo_threshold(threshold_pct=0.85)
    assert all(r["route_id"] != "r-safe" for r in results)


# ---------------------------------------------------------------------------
# A7: eval coverage gaps
# ---------------------------------------------------------------------------

def test_a7_returns_low_coverage_types() -> None:
    store = MockArtifactStore([
        {"artifact_type": "eval_coverage_summary", "artifact_type": "policy_bundle_artifact", "coverage_pct": 40, "uncovered_cases": 10},
        {"artifact_type": "eval_coverage_summary", "artifact_type": "judgment_record", "coverage_pct": 95, "uncovered_cases": 0},
    ])
    qs = DashboardQuerySurfaces(store)
    results = qs.query_eval_coverage_gaps()
    assert all(r["coverage_pct"] < 80 for r in results)


# ---------------------------------------------------------------------------
# A8: promotion readiness blockers
# ---------------------------------------------------------------------------

def test_a8_returns_blocked_routes() -> None:
    store = MockArtifactStore([
        {"artifact_type": "promotion_readiness_artifact", "route_id": "r-blocked", "is_blocked": True, "blocker_type": "eval_gap", "blocker_detail": "missing evals"},
        {"artifact_type": "promotion_readiness_artifact", "route_id": "r-ok", "is_blocked": False},
    ])
    qs = DashboardQuerySurfaces(store)
    results = qs.query_promotion_readiness_blockers()
    assert all(r["route_id"] == "r-blocked" for r in results)


# ---------------------------------------------------------------------------
# A.1.1: failure patterns by context class
# ---------------------------------------------------------------------------

def test_a11_clusters_by_context_class() -> None:
    store = MockArtifactStore([
        {"artifact_type": "postmortem_artifact", "context_class": "high-risk", "failure_pattern": "timeout"},
        {"artifact_type": "postmortem_artifact", "context_class": "high-risk", "failure_pattern": "timeout"},
        {"artifact_type": "postmortem_artifact", "context_class": "low-risk", "failure_pattern": "schema_mismatch"},
    ])
    qs = DashboardQuerySurfaces(store)
    results = qs.query_top_failure_patterns_by_context_class()
    high_risk = [r for r in results if r["context_class"] == "high-risk"]
    assert high_risk[0]["incident_count"] == 2


# ---------------------------------------------------------------------------
# A.1.2: incident drill
# ---------------------------------------------------------------------------

def test_a12_drill_returns_completed_status() -> None:
    store = MockArtifactStore([
        {"artifact_type": "postmortem_artifact", "incident_id": "inc-001", "context_class": "high-risk"},
        {"artifact_type": "eval_case"},
        {"artifact_type": "eval_case"},
    ])
    qs = DashboardQuerySurfaces(store)
    result = qs.query_incident_drill("inc-001")
    assert result["drill_status"] == "completed"
    assert result["evals_run"] == 2


def test_a12_missing_incident_raises() -> None:
    qs = DashboardQuerySurfaces(MockArtifactStore([]))
    with pytest.raises(RuntimeError, match="A.1.2 query failed"):
        qs.query_incident_drill("no-such-id")


# ---------------------------------------------------------------------------
# A.1.3: reviewer bias matrix
# ---------------------------------------------------------------------------

def test_a13_detects_reviewer_disagreement() -> None:
    store = MockArtifactStore([
        {"artifact_type": "human_review_outcome", "artifact_id": "art-1", "reviewer_id": "rev-A", "outcome": "approve"},
        {"artifact_type": "human_review_outcome", "artifact_id": "art-1", "reviewer_id": "rev-B", "outcome": "reject"},
    ])
    qs = DashboardQuerySurfaces(store)
    results = qs.query_reviewer_bias_matrix()
    assert len(results) == 1
    assert results[0]["disagreement_rate"] == 1.0


def test_a13_agreement_produces_zero_rate() -> None:
    store = MockArtifactStore([
        {"artifact_type": "human_review_outcome", "artifact_id": "art-2", "reviewer_id": "rev-A", "outcome": "approve"},
        {"artifact_type": "human_review_outcome", "artifact_id": "art-2", "reviewer_id": "rev-B", "outcome": "approve"},
    ])
    qs = DashboardQuerySurfaces(store)
    results = qs.query_reviewer_bias_matrix()
    assert results[0]["disagreement_rate"] == 0.0


# ---------------------------------------------------------------------------
# A.1.4: policy coverage delta
# ---------------------------------------------------------------------------

def test_a14_returns_gained_and_lost() -> None:
    store = MockArtifactStore([
        {"artifact_type": "eval_coverage_summary", "artifact_type": "policy_bundle", "coverage_pct": 90},
    ])
    qs = DashboardQuerySurfaces(store)
    result = qs.query_policy_coverage_delta()
    assert "gained_coverage" in result
    assert "lost_coverage" in result
    assert "timestamp" in result


# ---------------------------------------------------------------------------
# A.1.5: artifact supersession lineage
# ---------------------------------------------------------------------------

def test_a15_traces_lineage_chain() -> None:
    store = MockArtifactStore([
        {"artifact_type": "artifact_supersession_record", "superseded_artifact_id": "policy-v1", "new_artifact_id": "policy-v2", "reason": "threshold update"},
        {"artifact_type": "artifact_supersession_record", "superseded_artifact_id": "policy-v2", "new_artifact_id": "policy-v3", "reason": "coverage fix"},
    ])
    qs = DashboardQuerySurfaces(store)
    result = qs.query_artifact_supersession_lineage("policy-v1")
    assert result["total_supersessions"] == 2
    assert result["current_active"] == "policy-v3"


def test_a15_no_supersession_returns_original() -> None:
    qs = DashboardQuerySurfaces(MockArtifactStore([]))
    result = qs.query_artifact_supersession_lineage("art-standalone")
    assert result["current_active"] == "art-standalone"
    assert result["total_supersessions"] == 0


def test_a15_cycle_protection() -> None:
    store = MockArtifactStore([
        {"artifact_type": "artifact_supersession_record", "superseded_artifact_id": "a", "new_artifact_id": "b", "reason": "x"},
        {"artifact_type": "artifact_supersession_record", "superseded_artifact_id": "b", "new_artifact_id": "a", "reason": "cycle"},
    ])
    qs = DashboardQuerySurfaces(store)
    result = qs.query_artifact_supersession_lineage("a")
    assert result["total_supersessions"] <= 2
