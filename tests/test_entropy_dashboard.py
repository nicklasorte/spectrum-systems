"""Tests for entropy dashboard."""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock
from spectrum_systems.observability.entropy_dashboard import EntropyDashboard


class TestEntropyDashboard:
    @pytest.fixture
    def mock_artifact_store(self):
        return Mock()

    @pytest.fixture
    def dashboard(self, mock_artifact_store):
        return EntropyDashboard(artifact_store=mock_artifact_store)

    def test_entropy_snapshot_schema_valid(self):
        import jsonschema
        with open('contracts/schemas/entropy-posture-snapshot.schema.json') as f:
            schema = json.load(f)

        snapshot = {
            'snapshot_id': 'snap_1',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'week_ending': (datetime.utcnow().date()).isoformat(),
            'metrics': {
                'decision_divergence': {'current': 0.05, 'trend': 'stable'},
                'exception_rate': {'current': 0.01},
                'trace_coverage': {'current': 99.9},
                'calibration_drift': {'current': 0.02},
                'override_hotspots': {'count': 0},
                'failure_to_eval_rate': {'current': 0.005}
            },
            'control_decisions': ['proceed'],
            'recommendation': 'All systems nominal'
        }
        jsonschema.validate(snapshot, schema)

    def test_critical_entropy_triggers_block(self, dashboard, mock_artifact_store):
        mock_artifact_store.query.side_effect = [
            [{'decision_divergence': 0.25}],
            [],
            [],
            [],
            [],
        ]

        snapshot = dashboard.generate_weekly_snapshot()
        assert 'block' in snapshot['control_decisions']

    def test_elevated_entropy_triggers_escalate(self, dashboard, mock_artifact_store):
        mock_artifact_store.query.side_effect = [
            [{'decision_divergence': 0.12}],
            [],
            [],
            [],
            [],
        ]

        snapshot = dashboard.generate_weekly_snapshot()
        assert 'escalate' in snapshot['control_decisions']

    def test_nominal_entropy_proceeds(self, dashboard, mock_artifact_store):
        mock_artifact_store.query.side_effect = [
            [{'decision_divergence': 0.05}],
            [],
            [{'coverage_percent': 99.95, 'slo_met': True}],
            [],
            [],
        ]

        snapshot = dashboard.generate_weekly_snapshot()
        assert 'proceed' in snapshot['control_decisions']
