"""Tests for override hotspot tracking."""

import pytest
from datetime import datetime
from unittest.mock import Mock
from spectrum_systems.governance.override_hotspot_manager import OverrideHotspotManager


class TestOverrideHotspot:
    @pytest.fixture
    def mock_artifact_store(self):
        return Mock()

    @pytest.fixture
    def manager(self, mock_artifact_store):
        return OverrideHotspotManager(artifact_store=mock_artifact_store)

    def test_hotspot_report_generated(self, manager, mock_artifact_store):
        mock_artifact_store.query.return_value = [
            {'affected_resource': 'eval_gate', 'exception_id': 'exc_1'},
            {'affected_resource': 'eval_gate', 'exception_id': 'exc_2'},
            {'affected_resource': 'policy_gate', 'exception_id': 'exc_3'},
        ]

        report = manager.generate_hotspot_report(30)
        assert report['total_overrides'] == 3
        assert len(report['hotspots']) == 2

    def test_high_risk_gates_detected(self, manager, mock_artifact_store):
        mock_artifact_store.query.return_value = [
            {'affected_resource': 'eval_gate', 'exception_id': f'exc_{i}'}
            for i in range(7)
        ]

        report = manager.generate_hotspot_report(30)
        assert 'eval_gate' in report['high_risk_gates']
