"""Tests for ArtifactIntelligenceLayer (C1-C10)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

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
                if item.get(key) != value:
                    match = False
                    break
            if match:
                results.append(item)
        return results[:limit]

    def put(self, artifact: Dict[str, Any], namespace: str = "") -> None:
        pass


# C1
def test_c1_route_block_count_index() -> None:
    store = MockArtifactStore([
        {"artifact_type": "control_response_log", "control_decision": "block", "route_id": "r-1"},
        {"artifact_type": "control_response_log", "control_decision": "block", "route_id": "r-1"},
        {"artifact_type": "control_response_log", "control_decision": "block", "route_id": "r-2"},
    ])
    ail = ArtifactIntelligenceLayer(store)
    ail.build_route_block_count_index()
    assert ail.get_route_block_count("r-1") == 2
    assert ail.get_route_block_count("r-2") == 1
    assert ail.get_route_block_count("r-missing") == 0


# C2
def test_c2_policy_override_count_index() -> None:
    store = MockArtifactStore([
        {"artifact_type": "override_hotspot_report", "hotspots": [{"gate_name": "gate-A", "override_count": 5}]},
        {"artifact_type": "override_hotspot_report", "hotspots": [{"gate_name": "gate-A", "override_count": 3}]},
    ])
    ail = ArtifactIntelligenceLayer(store)
    ail.build_policy_override_count_index()
    assert ail.get_policy_override_count("gate-A") == 8


# C3
def test_c3_context_source_contradiction_index() -> None:
    store = MockArtifactStore([
        {"artifact_type": "contradiction_spike", "context_source": "src-X", "contradiction_count": 10},
        {"artifact_type": "contradiction_spike", "context_source": "src-X", "contradiction_count": 5},
        {"artifact_type": "contradiction_spike", "context_source": "src-Y", "contradiction_count": 2},
    ])
    ail = ArtifactIntelligenceLayer(store)
    ail.build_context_source_contradiction_index()
    assert ail.get_context_source_contradiction_count("src-X") == 15
    assert ail.get_context_source_contradiction_count("src-Y") == 2


# C4
def test_c4_judge_disagreement_rate_index() -> None:
    store = MockArtifactStore([
        {"artifact_type": "judge_disagreement_report", "judge_id": "j-1", "disagreement_rate": 0.25},
        {"artifact_type": "judge_disagreement_report", "judge_id": "j-2", "disagreement_rate": 0.05},
    ])
    ail = ArtifactIntelligenceLayer(store)
    ail.build_judge_disagreement_rate_index()
    assert ail.get_judge_disagreement_rate("j-1") == 0.25
    assert ail.get_judge_disagreement_rate("j-missing") == 0.0


# C5
def test_c5_artifact_type_failure_count_index() -> None:
    store = MockArtifactStore([
        {"artifact_type": "postmortem_artifact", "primary_artifact_type": "policy_bundle"},
        {"artifact_type": "postmortem_artifact", "primary_artifact_type": "policy_bundle"},
        {"artifact_type": "postmortem_artifact", "primary_artifact_type": "judgment_record"},
    ])
    ail = ArtifactIntelligenceLayer(store)
    ail.build_artifact_type_failure_count_index()
    assert ail.get_artifact_type_failure_count("policy_bundle") == 2
    assert ail.get_artifact_type_failure_count("judgment_record") == 1


# C6
def test_c6_route_cost_trend_index() -> None:
    store = MockArtifactStore([
        {"artifact_type": "cost_budget_status", "route_id": "r-1", "cost_per_promotion": 100.0},
        {"artifact_type": "cost_budget_status", "route_id": "r-1", "cost_per_promotion": 130.0},
    ])
    ail = ArtifactIntelligenceLayer(store)
    ail.build_route_cost_trend_index()
    trend = ail.get_route_cost_trend("r-1")
    assert trend is not None
    assert trend["trend_pct"] == pytest.approx(30.0)


def test_c6_single_data_point_not_indexed() -> None:
    store = MockArtifactStore([
        {"artifact_type": "cost_budget_status", "route_id": "r-solo", "cost_per_promotion": 50.0},
    ])
    ail = ArtifactIntelligenceLayer(store)
    ail.build_route_cost_trend_index()
    assert ail.get_route_cost_trend("r-solo") is None


# C7
def test_c7_incident_context_class_index() -> None:
    store = MockArtifactStore([
        {"artifact_type": "postmortem_artifact", "incident_id": "inc-1", "context_class": "high-risk"},
    ])
    ail = ArtifactIntelligenceLayer(store)
    ail.build_incident_context_class_index()
    assert ail.get_incident_context_class("inc-1") == "high-risk"
    assert ail.get_incident_context_class("missing") == "unknown"


# C8
def test_c8_reviewer_disagreement_count_index() -> None:
    store = MockArtifactStore([
        {"artifact_type": "human_review_outcome", "artifact_id": "art-1", "reviewer_id": "rev-A", "outcome": "approve"},
        {"artifact_type": "human_review_outcome", "artifact_id": "art-1", "reviewer_id": "rev-B", "outcome": "reject"},
    ])
    ail = ArtifactIntelligenceLayer(store)
    ail.build_reviewer_disagreement_count_index()
    assert ail.get_reviewer_disagreement_count("rev-A") == 1
    assert ail.get_reviewer_disagreement_count("rev-B") == 1


# C9
def test_c9_artifact_supersession_chain_index() -> None:
    store = MockArtifactStore([
        {"artifact_type": "artifact_supersession_record", "superseded_artifact_id": "p-v1", "new_artifact_id": "p-v2"},
        {"artifact_type": "artifact_supersession_record", "superseded_artifact_id": "p-v2", "new_artifact_id": "p-v3"},
    ])
    ail = ArtifactIntelligenceLayer(store)
    ail.build_artifact_supersession_chain_index()
    assert ail.get_supersession_chain_length("p-v1") == 2


# C10
def test_c10_control_decision_effectiveness_index() -> None:
    store = MockArtifactStore([
        {"artifact_type": "control_response_log", "control_decision": "block", "status": "active"},
        {"artifact_type": "control_response_log", "control_decision": "block", "status": "reversed"},
        {"artifact_type": "control_response_log", "control_decision": "freeze", "status": "active"},
    ])
    ail = ArtifactIntelligenceLayer(store)
    ail.build_control_decision_effectiveness_index()
    block = ail.get_control_decision_effectiveness("block")
    assert block is not None
    assert block["total"] == 2
    assert block["false_positive_rate"] == pytest.approx(0.5)


def test_build_all_indexes_returns_status_map() -> None:
    store = MockArtifactStore([])
    ail = ArtifactIntelligenceLayer(store)
    status = ail.build_all_indexes()
    assert len(status) == 10
    assert all(v == "built" for v in status.values())


import pytest
