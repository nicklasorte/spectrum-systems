"""Tests for ControlResponseExecutor (I1-I5)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from spectrum_systems.dashboard.control_response_executor import ControlResponseExecutor


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
        self._data.append(artifact)


# I1: Freeze route
def test_i1_freeze_writes_log_with_correct_decision() -> None:
    store = MockArtifactStore()
    executor = ControlResponseExecutor(store, signer_id="cde-test")
    log = executor.freeze_route("r-1", "calibration_exceeded", "Calibration error > 10%.")
    assert log["control_decision"] == "freeze"
    assert log["route_id"] == "r-1"
    assert log["signer_id"] == "cde-test"
    assert log["status"] == "active"
    assert "log_id" in log
    assert "timestamp" in log


def test_i1_freeze_immutable_artifact_written_to_store() -> None:
    store = MockArtifactStore()
    executor = ControlResponseExecutor(store)
    executor.freeze_route("r-1", "signal", "Route frozen due to drift signal exceeding threshold.")
    control_logs = [w for w in store._written if w.get("artifact_type") == "control_response_log"]
    assert len(control_logs) == 1


# I2: Block artifact
def test_i2_block_writes_block_decision() -> None:
    store = MockArtifactStore()
    executor = ControlResponseExecutor(store)
    log = executor.block_artifact("r-2", "schema_violation", "Artifact failed schema validation on required fields.")
    assert log["control_decision"] == "block"
    assert log["route_id"] == "r-2"


# I3: Escalate
def test_i3_escalate_writes_escalate_decision() -> None:
    store = MockArtifactStore()
    executor = ControlResponseExecutor(store)
    log = executor.escalate_for_review("r-3", "judge_disagreement", "Disagreement rate exceeded 20% threshold value.")
    assert log["control_decision"] == "escalate"


# I4: Warn
def test_i4_warn_writes_warn_decision() -> None:
    store = MockArtifactStore()
    executor = ControlResponseExecutor(store)
    log = executor.warn_operator("r-4", "cost_trend", "Route cost per promotion increasing by 12% this week.")
    assert log["control_decision"] == "warn"


# I5: Allow with rationale
def test_i5_allow_writes_allow_decision_with_rationale() -> None:
    store = MockArtifactStore()
    executor = ControlResponseExecutor(store)
    log = executor.allow_with_rationale("r-5", "manual_review", "Human reviewer approved after thorough evidence review.")
    assert log["control_decision"] == "allow"
    assert len(log["decision_rationale"]) > 10


# Unfreeze workflow
def test_unfreeze_requires_existing_freeze_log() -> None:
    store = MockArtifactStore()
    executor = ControlResponseExecutor(store)
    with pytest.raises(ValueError, match="not found"):
        executor.unfreeze_route("no-such-log", "r-1", "approver-1", "Reviewed and cleared the drift signal.")


def test_unfreeze_requires_freeze_decision() -> None:
    store = MockArtifactStore([
        {
            "artifact_type": "control_response_log",
            "log_id": "crl-not-freeze",
            "control_decision": "block",
            "route_id": "r-1",
            "signer_id": "cde-test",
            "status": "active",
        }
    ])
    executor = ControlResponseExecutor(store)
    with pytest.raises(ValueError, match="not a freeze decision"):
        executor.unfreeze_route("crl-not-freeze", "r-1", "approver-1", "Attempted unfreeze of non-freeze log.")


def test_unfreeze_writes_reversal_record_and_allow_log() -> None:
    store = MockArtifactStore([
        {
            "artifact_type": "control_response_log",
            "log_id": "crl-freeze-001",
            "control_decision": "freeze",
            "route_id": "r-frozen",
            "signer_id": "cde-test",
            "status": "active",
            "timestamp": "2026-04-22T08:00:00Z",
        }
    ])
    executor = ControlResponseExecutor(store, signer_id="cde-test")
    allow_log = executor.unfreeze_route(
        "crl-freeze-001", "r-frozen", "approver-human", "Investigation complete, drift signal was transient."
    )
    assert allow_log["control_decision"] == "allow"
    reversal_records = [w for w in store._written if w.get("artifact_type") == "control_response_log_reversal"]
    assert len(reversal_records) == 1
    assert reversal_records[0]["approver_id"] == "approver-human"


# get_active_freezes
def test_get_active_freezes_returns_only_freeze_active() -> None:
    store = MockArtifactStore([
        {"artifact_type": "control_response_log", "control_decision": "freeze", "status": "active", "route_id": "r-a"},
        {"artifact_type": "control_response_log", "control_decision": "freeze", "status": "reversed", "route_id": "r-b"},
        {"artifact_type": "control_response_log", "control_decision": "block", "status": "active", "route_id": "r-c"},
    ])
    executor = ControlResponseExecutor(store)
    freezes = executor.get_active_freezes()
    assert len(freezes) == 1
    assert freezes[0]["route_id"] == "r-a"


# Immutability: log_ids are unique
def test_log_ids_are_unique() -> None:
    store = MockArtifactStore()
    executor = ControlResponseExecutor(store)
    log1 = executor.freeze_route("r-1", "signal", "Freeze because calibration drift exceeded 10% over 24 hours.")
    log2 = executor.freeze_route("r-2", "signal", "Freeze because calibration drift exceeded 10% over 24 hours.")
    assert log1["log_id"] != log2["log_id"]
