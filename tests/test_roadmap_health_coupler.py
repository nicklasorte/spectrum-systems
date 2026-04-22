"""Tests for health-driven roadmap coupling."""

import pytest
from datetime import datetime
from unittest.mock import Mock
from spectrum_systems.planning.roadmap_health_coupler import RoadmapHealthCoupler


class TestRoadmapHealthCoupler:
    @pytest.fixture
    def mock_artifact_store(self):
        return Mock()

    @pytest.fixture
    def coupler(self, mock_artifact_store):
        return RoadmapHealthCoupler(artifact_store=mock_artifact_store)

    def test_critical_health_pauses_non_critical_work(self, coupler, mock_artifact_store):
        mock_artifact_store.query.return_value = [
            {
                'metrics': {
                    'decision_divergence': {'current': 0.20},
                    'exception_rate': {'current': 0.06}
                }
            }
        ]

        report = coupler.generate_priority_report()

        assert report['current_health'] == 'critical'
        assert 'emergency_review' in report['prioritized_items']
        assert 'new_features' in report['paused_items']

    def test_healthy_status_proceeds_normally(self, coupler, mock_artifact_store):
        mock_artifact_store.query.return_value = [
            {
                'metrics': {
                    'decision_divergence': {'current': 0.05},
                    'exception_rate': {'current': 0.01}
                }
            }
        ]

        report = coupler.generate_priority_report()
        assert report['current_health'] == 'healthy'
        assert len(report['paused_items']) == 0
