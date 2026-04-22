"""Tests for EffectivenessTracker (J1-J5)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from spectrum_systems.dashboard.effectiveness_tracker import EffectivenessTracker


class MockArtifactStore:
    def __init__(self, data: Optional[List[Dict[str, Any]]] = None) -> None:
        self._data = data or []
        self._written: List[Dict[str, Any]] = []

    def query(self, filters: Dict[str, Any], limit: int = 10000) -> List[Dict[str, Any]]:
        results = []
        for item in self._data:
            match = True
            for key, value in filters.items():
                if key in ("recency_days", "control_decision_in"):
                    continue
                if item.get(key) != value:
                    match = False
                    break
            if match:
                results.append(item)
        return results[:limit]

    def put(self, artifact: Dict[str, Any], namespace: str = "") -> None:
        self._written.append(artifact)
        self._data.append(artifact)


# J1: Frozen route recovery time
def test_j1_recovery_time_computed_correctly() -> None:
    store = MockArtifactStore([
        {
            "artifact_type": "control_response_log_reversal",
            "original_log_id": "crl-freeze-1",
            "timestamp": "2026-04-22T11:00:00Z",
        },
        {
            "artifact_type": "control_response_log",
            "log_id": "crl-freeze-1",
            "control_decision": "freeze",
            "timestamp": "2026-04-22T10:00:00Z",
        },
    ])
    tracker = EffectivenessTracker(store)
    metric = tracker.measure_frozen_route_recovery_time(period="daily")
    assert metric["metric_type"] == "frozen_route_recovery_time"
    assert metric["metric_value"] == pytest.approx(60.0)


def test_j1_no_reversals_returns_zero() -> None:
    store = MockArtifactStore([])
    tracker = EffectivenessTracker(store)
    metric = tracker.measure_frozen_route_recovery_time()
    assert metric["metric_value"] == 0.0


# J2: False positive rate
def test_j2_false_positive_rate_calculated() -> None:
    store = MockArtifactStore([
        {"artifact_type": "control_response_log", "status": "active"},
        {"artifact_type": "control_response_log", "status": "reversed"},
        {"artifact_type": "control_response_log", "status": "active"},
        {"artifact_type": "control_response_log", "status": "reversed"},
    ])
    tracker = EffectivenessTracker(store)
    metric = tracker.measure_false_positive_rate(period="daily")
    assert metric["metric_type"] == "false_positive_rate"
    assert metric["metric_value"] == pytest.approx(0.5)


def test_j2_zero_logs_returns_zero_fpr() -> None:
    store = MockArtifactStore([])
    tracker = EffectivenessTracker(store)
    metric = tracker.measure_false_positive_rate()
    assert metric["metric_value"] == 0.0


# J3: Incidents prevented
def test_j3_counts_blocks_without_postmortem() -> None:
    store = MockArtifactStore([
        {"artifact_type": "control_response_log", "control_decision": "block", "route_id": "r-safe"},
        {"artifact_type": "control_response_log", "control_decision": "block", "route_id": "r-failed"},
        {"artifact_type": "postmortem_artifact", "route_id": "r-failed"},
    ])
    tracker = EffectivenessTracker(store)
    metric = tracker.measure_incidents_prevented(period="daily")
    assert metric["metric_type"] == "incident_prevented"
    assert metric["metric_value"] == pytest.approx(1.0)


def test_j3_all_blocks_have_postmortem_returns_zero() -> None:
    store = MockArtifactStore([
        {"artifact_type": "control_response_log", "control_decision": "block", "route_id": "r-1"},
        {"artifact_type": "postmortem_artifact", "route_id": "r-1"},
    ])
    tracker = EffectivenessTracker(store)
    metric = tracker.measure_incidents_prevented()
    assert metric["metric_value"] == 0.0


# J4: Escalation resolution time
def test_j4_no_escalations_returns_zero() -> None:
    store = MockArtifactStore([])
    tracker = EffectivenessTracker(store)
    metric = tracker.measure_escalation_resolution_time()
    assert metric["metric_type"] == "escalation_resolution_time"
    assert metric["metric_value"] == 0.0


def test_j4_metric_emitted_with_correct_type() -> None:
    store = MockArtifactStore([
        {
            "artifact_type": "control_response_log",
            "control_decision": "escalate",
            "route_id": "r-esc",
            "timestamp": "2026-04-22T09:00:00Z",
        }
    ])
    tracker = EffectivenessTracker(store)
    metric = tracker.measure_escalation_resolution_time(period="daily")
    assert metric["metric_type"] == "escalation_resolution_time"


# J5: Override effectiveness
def test_j5_no_overrides_returns_zero() -> None:
    store = MockArtifactStore([])
    tracker = EffectivenessTracker(store)
    metric = tracker.measure_override_effectiveness()
    assert metric["metric_type"] == "override_effectiveness"
    assert metric["metric_value"] == 0.0


def test_j5_all_overrides_without_postmortem_is_fully_effective() -> None:
    store = MockArtifactStore([
        {"artifact_type": "control_response_log", "trigger_signal": "manual_unfreeze", "route_id": "r-good"},
        {"artifact_type": "control_response_log", "trigger_signal": "manual_unfreeze", "route_id": "r-also-good"},
    ])
    tracker = EffectivenessTracker(store)
    metric = tracker.measure_override_effectiveness(period="weekly")
    assert metric["metric_value"] == pytest.approx(1.0)


# Immutability: metric_ids are unique
def test_metric_ids_are_unique() -> None:
    store = MockArtifactStore([])
    tracker = EffectivenessTracker(store)
    m1 = tracker.measure_false_positive_rate()
    m2 = tracker.measure_false_positive_rate()
    assert m1["metric_id"] != m2["metric_id"]


# measure_all returns 5 metrics
def test_measure_all_returns_five_metrics() -> None:
    store = MockArtifactStore([])
    tracker = EffectivenessTracker(store)
    results = tracker.measure_all(period="daily")
    assert len(results) == 5
    metric_types = {r["metric_type"] for r in results}
    expected = {"frozen_route_recovery_time", "false_positive_rate", "incident_prevented", "escalation_resolution_time", "override_effectiveness"}
    assert metric_types == expected
