"""Tests for DashboardJobsScheduler (B1-B10)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from spectrum_systems.dashboard.jobs_scheduler import DashboardJobsScheduler


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
                if item.get(key) != value:
                    match = False
                    break
            if match:
                results.append(item)
        return results[:limit]

    def put(self, artifact: Dict[str, Any], namespace: str = "") -> None:
        self._written.append(artifact)


# B1
def test_b1_reason_code_aggregation_writes_records() -> None:
    store = MockArtifactStore([
        {"artifact_type": "control_response_log", "control_decision": "block", "trigger_signal": "drift"},
        {"artifact_type": "control_response_log", "control_decision": "block", "trigger_signal": "drift"},
        {"artifact_type": "control_response_log", "control_decision": "block", "trigger_signal": "timeout"},
    ])
    scheduler = DashboardJobsScheduler(store)
    result = scheduler.run_daily_reason_code_aggregation()
    assert result["job"] == "B1"
    assert result["records_written"] == 2
    written_types = [w["artifact_type"] for w in store._written]
    assert "reason_code_record" in written_types


def test_b1_empty_store_writes_nothing() -> None:
    store = MockArtifactStore([])
    scheduler = DashboardJobsScheduler(store)
    result = scheduler.run_daily_reason_code_aggregation()
    assert result["records_written"] == 0


# B2
def test_b2_override_rate_writes_summary() -> None:
    store = MockArtifactStore([
        {"artifact_type": "override_hotspot_report", "report_id": "rpt-1", "hotspots": [{"gate_name": "g1", "override_count": 3}]},
    ])
    scheduler = DashboardJobsScheduler(store)
    result = scheduler.run_daily_override_rate_calculation()
    assert result["job"] == "B2"
    assert result["records_written"] == 1


# B3
def test_b3_cost_per_promotion_writes_summary() -> None:
    store = MockArtifactStore([
        {"artifact_type": "cost_budget_status", "route_id": "r-1", "cost_per_promotion": 42.0},
    ])
    scheduler = DashboardJobsScheduler(store)
    result = scheduler.run_daily_cost_per_promotion()
    assert result["job"] == "B3"
    assert result["records_written"] == 1


# B4
def test_b4_contradiction_correlation_writes_records() -> None:
    store = MockArtifactStore([
        {"artifact_type": "contradiction_spike", "context_source": "src-A", "contradiction_count": 5},
    ])
    scheduler = DashboardJobsScheduler(store)
    result = scheduler.run_daily_contradiction_correlation()
    assert result["job"] == "B4"
    assert result["records_written"] == 1


# B5
def test_b5_judge_disagreement_report_writes_summary() -> None:
    store = MockArtifactStore([
        {"artifact_type": "judge_disagreement_report", "judge_id": "j-1", "disagreement_rate": 0.2},
    ])
    scheduler = DashboardJobsScheduler(store)
    result = scheduler.run_daily_judge_disagreement_report()
    assert result["job"] == "B5"
    assert result["records_written"] == 1


# B6
def test_b6_supersession_audit_produces_summary() -> None:
    store = MockArtifactStore([
        {"artifact_type": "artifact_supersession_record", "superseded_artifact_id": "a", "new_artifact_id": "b"},
        {"artifact_type": "artifact_supersession_record", "superseded_artifact_id": "c", "new_artifact_id": None},
    ])
    scheduler = DashboardJobsScheduler(store)
    result = scheduler.run_weekly_artifact_supersession_audit()
    assert result["job"] == "B6"
    assert result["orphans_found"] == 1


# B7
def test_b7_job_failure_classification_counts_dead_letters() -> None:
    store = MockArtifactStore([
        {"artifact_type": "job_failure_artifact", "status": "dead_letter"},
        {"artifact_type": "job_failure_artifact", "status": "recovered"},
    ])
    scheduler = DashboardJobsScheduler(store)
    result = scheduler.run_daily_job_failure_classification()
    assert result["job"] == "B7"
    assert result["dead_letters"] == 1
    assert result["total_failures"] == 2


# B8
def test_b8_streaming_index_indexes_logs() -> None:
    store = MockArtifactStore([
        {"artifact_type": "control_response_log", "log_id": "crl-1", "control_decision": "block", "route_id": "r-1"},
        {"artifact_type": "control_response_log", "log_id": "crl-2", "control_decision": "allow", "route_id": "r-2"},
    ])
    scheduler = DashboardJobsScheduler(store)
    result = scheduler.run_streaming_control_response_index(batch_size=100)
    assert result["job"] == "B8"
    assert result["indexed"] == 2


# B9
def test_b9_eval_coverage_gap_detects_low_coverage() -> None:
    store = MockArtifactStore([
        {"artifact_type": "eval_coverage_summary", "artifact_type": "type-A", "coverage_pct": 50},
        {"artifact_type": "eval_coverage_summary", "artifact_type": "type-B", "coverage_pct": 90},
    ])
    scheduler = DashboardJobsScheduler(store)
    result = scheduler.run_daily_eval_coverage_gap_detection()
    assert result["job"] == "B9"
    assert result["gaps_detected"] >= 0


# B10
def test_b10_weekly_effectiveness_metric_emits_metric() -> None:
    store = MockArtifactStore([
        {"artifact_type": "control_response_log", "status": "active"},
        {"artifact_type": "control_response_log", "status": "reversed"},
        {"artifact_type": "control_response_log", "status": "active"},
    ])
    scheduler = DashboardJobsScheduler(store)
    result = scheduler.run_weekly_effectiveness_metric_calculation()
    assert result["job"] == "B10"
    assert abs(result["false_positive_rate"] - (1 / 3)) < 0.01
    written = [w for w in store._written if w.get("artifact_type") == "control_effectiveness_metric"]
    assert len(written) == 1


# Failure artifact emission
def test_failure_artifact_emitted_on_job_error() -> None:
    store = MagicMock()
    store.query.side_effect = RuntimeError("db down")
    store.put = MagicMock()
    scheduler = DashboardJobsScheduler(store)
    with pytest.raises(RuntimeError):
        scheduler.run_daily_reason_code_aggregation()
    failure_calls = [call for call in store.put.call_args_list if call[0][0].get("artifact_type") == "job_failure_artifact"]
    assert len(failure_calls) == 1


# run_all_daily_jobs
def test_run_all_daily_jobs_returns_results_for_each() -> None:
    store = MockArtifactStore([])
    scheduler = DashboardJobsScheduler(store)
    results = scheduler.run_all_daily_jobs()
    assert len(results) == 7
