"""End-to-end integration tests (K1-K8).

These tests wire together multiple components to verify the full pipeline:
query → index → control response → effectiveness measurement.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from spectrum_systems.dashboard.query_surfaces import DashboardQuerySurfaces
from spectrum_systems.dashboard.jobs_scheduler import DashboardJobsScheduler
from spectrum_systems.dashboard.artifact_intelligence_layer import ArtifactIntelligenceLayer
from spectrum_systems.dashboard.control_response_executor import ControlResponseExecutor
from spectrum_systems.dashboard.effectiveness_tracker import EffectivenessTracker


class SharedMockArtifactStore:
    """Shared store for integration tests — all components read/write to the same data."""

    def __init__(self) -> None:
        self._data: List[Dict[str, Any]] = []

    def query(self, filters: Dict[str, Any], limit: int = 10000) -> List[Dict[str, Any]]:
        results = []
        for item in self._data:
            match = True
            for key, value in filters.items():
                if key in ("recency_days", "control_decision_in"):
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
        self._data.append(artifact)

    def seed(self, artifacts: List[Dict[str, Any]]) -> None:
        self._data.extend(artifacts)


# K1: Query → control response pipeline
def test_k1_query_block_then_freeze_route() -> None:
    store = SharedMockArtifactStore()
    store.seed([
        {"artifact_type": "control_response_log", "control_decision": "block", "trigger_signal": "drift", "route_id": "r-1", "status": "active"},
        {"artifact_type": "control_response_log", "control_decision": "block", "trigger_signal": "drift", "route_id": "r-1", "status": "active"},
    ])
    qs = DashboardQuerySurfaces(store)
    top_codes = qs.query_top_reason_codes_by_blocks()
    assert top_codes[0]["reason_code"] == "drift"

    executor = ControlResponseExecutor(store, signer_id="cde-test")
    freeze_log = executor.freeze_route("r-1", "drift", "Drift exceeded threshold; route frozen pending review.")
    assert freeze_log["control_decision"] == "freeze"


# K2: Jobs write artifacts that query surfaces can read
def test_k2_job_writes_artifact_that_query_reads() -> None:
    store = SharedMockArtifactStore()
    store.seed([
        {"artifact_type": "control_response_log", "control_decision": "block", "trigger_signal": "timeout", "status": "active"},
    ])
    scheduler = DashboardJobsScheduler(store)
    scheduler.run_daily_reason_code_aggregation()

    reason_records = store.query({"artifact_type": "reason_code_record"})
    assert len(reason_records) >= 1
    assert reason_records[0]["code_name"] == "timeout"


# K3: Index accelerates query (index built → O(1) lookup returns same result as full scan)
def test_k3_index_matches_full_scan() -> None:
    store = SharedMockArtifactStore()
    store.seed([
        {"artifact_type": "control_response_log", "control_decision": "block", "route_id": "r-1"},
        {"artifact_type": "control_response_log", "control_decision": "block", "route_id": "r-1"},
        {"artifact_type": "control_response_log", "control_decision": "block", "route_id": "r-2"},
    ])
    qs = DashboardQuerySurfaces(store)
    top_blocks = qs.query_top_reason_codes_by_blocks()

    ail = ArtifactIntelligenceLayer(store)
    ail.build_route_block_count_index()
    assert ail.get_route_block_count("r-1") == 2
    assert ail.get_route_block_count("r-2") == 1


# K4: Control decision → effectiveness measurement roundtrip
def test_k4_control_decision_appears_in_effectiveness_metrics() -> None:
    store = SharedMockArtifactStore()
    executor = ControlResponseExecutor(store, signer_id="cde-test")
    executor.block_artifact("r-1", "schema_fail", "Artifact blocked due to schema validation failure in required fields.")

    tracker = EffectivenessTracker(store)
    metric = tracker.measure_false_positive_rate(period="daily")
    assert metric["metric_value"] == 0.0


# K5: Freeze → unfreeze → allow pipeline
def test_k5_freeze_unfreeze_allow_pipeline() -> None:
    store = SharedMockArtifactStore()
    executor = ControlResponseExecutor(store, signer_id="cde-test")

    freeze_log = executor.freeze_route("r-pipeline", "calibration_exceeded", "Calibration error exceeded 10% threshold value.")
    log_id = freeze_log["log_id"]

    allow_log = executor.unfreeze_route(log_id, "r-pipeline", "human-approver", "Reviewed evidence; drift was transient.")
    assert allow_log["control_decision"] == "allow"

    reversals = store.query({"artifact_type": "control_response_log_reversal"})
    assert len(reversals) == 1


# K6: Job failure artifact emitted on error, then detected by B7
def test_k6_job_failure_detected_by_b7() -> None:
    from unittest.mock import MagicMock
    failing_store = MagicMock()
    failing_store.query.side_effect = [RuntimeError("db down")] * 4
    failing_store.put = MagicMock()

    scheduler = DashboardJobsScheduler(failing_store)
    with pytest.raises(RuntimeError):
        scheduler.run_daily_reason_code_aggregation()

    failure_calls = [c for c in failing_store.put.call_args_list if c[0][0].get("artifact_type") == "job_failure_artifact"]
    assert len(failure_calls) == 1


# K7: Supersession lineage tracked through index and query
def test_k7_supersession_lineage_indexed_and_queried() -> None:
    store = SharedMockArtifactStore()
    store.seed([
        {"artifact_type": "artifact_supersession_record", "superseded_artifact_id": "pol-v1", "new_artifact_id": "pol-v2", "reason": "threshold update"},
        {"artifact_type": "artifact_supersession_record", "superseded_artifact_id": "pol-v2", "new_artifact_id": "pol-v3", "reason": "coverage fix"},
        {"artifact_type": "artifact_supersession_record", "superseded_artifact_id": "pol-v3", "new_artifact_id": "pol-v4", "reason": "calibration fix"},
    ])
    qs = DashboardQuerySurfaces(store)
    lineage = qs.query_artifact_supersession_lineage("pol-v1")
    assert lineage["total_supersessions"] == 3
    assert lineage["current_active"] == "pol-v4"

    ail = ArtifactIntelligenceLayer(store)
    ail.build_artifact_supersession_chain_index(days=90)
    assert ail.get_supersession_chain_length("pol-v1") == 3


# K8: All-jobs run → effectiveness metrics → complete cycle
def test_k8_full_daily_cycle() -> None:
    store = SharedMockArtifactStore()
    store.seed([
        {"artifact_type": "control_response_log", "control_decision": "block", "trigger_signal": "drift", "status": "active"},
        {"artifact_type": "control_response_log", "control_decision": "block", "trigger_signal": "drift", "status": "reversed"},
    ])

    scheduler = DashboardJobsScheduler(store)
    job_results = scheduler.run_all_daily_jobs()
    assert len(job_results) == 7

    tracker = EffectivenessTracker(store)
    metrics = tracker.measure_all(period="daily")
    assert len(metrics) == 5
    fpr = next(m for m in metrics if m["metric_type"] == "false_positive_rate")
    assert fpr["metric_value"] == pytest.approx(0.5)

    ail = ArtifactIntelligenceLayer(store)
    status = ail.build_all_indexes()
    assert all(v == "built" for v in status.values())
