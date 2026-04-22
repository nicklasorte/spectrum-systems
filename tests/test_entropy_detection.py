"""Tests for entropy detection signals surfaced through the dashboard (D1-D8).

These tests validate that the query layer correctly surfaces entropy signals:
silent drift, eval blind spots, overconfidence, schema gaps, and learning gaps.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pytest

from spectrum_systems.dashboard.query_surfaces import DashboardQuerySurfaces
from spectrum_systems.dashboard.artifact_intelligence_layer import ArtifactIntelligenceLayer


class MockArtifactStore:
    def __init__(self, data: Optional[List[Dict[str, Any]]] = None) -> None:
        self._data = data or []
        self._written: List[Dict[str, Any]] = []

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
        self._written.append(artifact)


# D1: Silent drift — rising contradiction trend undetected without A4
def test_d1_silent_drift_detected_via_contradiction_query() -> None:
    store = MockArtifactStore([
        {"artifact_type": "contradiction_spike", "context_source": "ctx-silent", "contradiction_count": 50},
    ])
    qs = DashboardQuerySurfaces(store)
    results = qs.query_context_source_contradiction_correlation()
    assert any(r["context_source"] == "ctx-silent" for r in results)


# D2: Exception accumulation — dead-letter job failures surfaced via B7
def test_d2_exception_accumulation_surfaced_as_dead_letters() -> None:
    from spectrum_systems.dashboard.jobs_scheduler import DashboardJobsScheduler
    store = MockArtifactStore([
        {"artifact_type": "job_failure_artifact", "status": "dead_letter"},
        {"artifact_type": "job_failure_artifact", "status": "dead_letter"},
        {"artifact_type": "job_failure_artifact", "status": "recovered"},
    ])
    scheduler = DashboardJobsScheduler(store)
    result = scheduler.run_daily_job_failure_classification()
    assert result["dead_letters"] == 2


# D3: Hidden logic creep — policy override rates rising without explanation
def test_d3_hidden_logic_creep_detected_via_a2() -> None:
    from unittest.mock import MagicMock
    store = MagicMock()
    store.query.side_effect = [
        [{"artifact_type": "override_hotspot_report", "hotspots": [{"gate_name": "creep-gate", "override_count": 2}]}],
        [{"artifact_type": "override_hotspot_report", "hotspots": [{"gate_name": "creep-gate", "override_count": 20}]}],
    ]
    store.put = MagicMock()
    qs = DashboardQuerySurfaces(store)
    results = qs.query_policies_with_rising_override_rates()
    assert any(r["policy"] == "creep-gate" for r in results)


# D4: Eval blind spots — coverage gaps exposed by A7
def test_d4_eval_blind_spots_detected() -> None:
    store = MockArtifactStore([
        {"artifact_type": "eval_coverage_summary", "covered_type": "blind-type", "coverage_pct": 10, "uncovered_cases": 50},
    ])
    qs = DashboardQuerySurfaces(store)
    results = qs.query_eval_coverage_gaps()
    assert len(results) >= 1


# D5: Overconfidence — judge disagreement drift rising (A5)
def test_d5_judge_overconfidence_detected() -> None:
    ts_old = (datetime.utcnow() - timedelta(days=20)).isoformat() + "Z"
    ts_new = (datetime.utcnow() - timedelta(days=1)).isoformat() + "Z"
    store = MockArtifactStore([
        {"artifact_type": "judge_disagreement_report", "judge_id": "j-overconf", "disagreement_rate": 0.05, "timestamp": ts_old},
        {"artifact_type": "judge_disagreement_report", "judge_id": "j-overconf", "disagreement_rate": 0.40, "timestamp": ts_new},
    ])
    qs = DashboardQuerySurfaces(store)
    results = qs.query_judge_human_disagreement_drift()
    j = next(r for r in results if r["judge_id"] == "j-overconf")
    assert j["trend"] == "rising"


# D6: Loss of causality — supersession chain broken (A.1.5)
def test_d6_causality_chain_traceable() -> None:
    store = MockArtifactStore([
        {"artifact_type": "artifact_supersession_record", "superseded_artifact_id": "cause-v1", "new_artifact_id": "cause-v2", "reason": "fix drift"},
    ])
    qs = DashboardQuerySurfaces(store)
    result = qs.query_artifact_supersession_lineage("cause-v1")
    assert result["total_supersessions"] == 1
    assert result["lineage_chain"][0]["reason"] == "fix drift"


# D7: Schema gaps — new artifact types without eval coverage (A.1.4)
def test_d7_new_artifact_type_without_coverage() -> None:
    store = MockArtifactStore([
        {"artifact_type": "eval_coverage_summary", "artifact_type": "new-schema-type", "coverage_pct": 0},
    ])
    qs = DashboardQuerySurfaces(store)
    result = qs.query_policy_coverage_delta()
    assert isinstance(result["new_artifact_types"], list)


# D8: Learning gap — failure patterns unclustered (A.1.1)
def test_d8_failure_pattern_clustering() -> None:
    store = MockArtifactStore([
        {"artifact_type": "postmortem_artifact", "context_class": "gap-class", "failure_pattern": "unclassified"},
        {"artifact_type": "postmortem_artifact", "context_class": "gap-class", "failure_pattern": "unclassified"},
    ])
    qs = DashboardQuerySurfaces(store)
    results = qs.query_top_failure_patterns_by_context_class()
    gap = next(r for r in results if r["context_class"] == "gap-class")
    assert gap["incident_count"] == 2
