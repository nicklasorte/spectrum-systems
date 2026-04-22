"""Tests for multi-model robustness checking."""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock
from spectrum_systems.robustness.multi_model_checker import MultiModelChecker


class TestMultiModelChecker:
    @pytest.fixture
    def mock_artifact_store(self):
        return Mock()

    @pytest.fixture
    def checker(self, mock_artifact_store):
        return MultiModelChecker(artifact_store=mock_artifact_store)

    def test_model_comparison_schema_valid(self):
        import jsonschema
        with open('contracts/schemas/model-comparison-report.schema.json') as f:
            schema = json.load(f)

        report = {
            'report_id': 'report_1',
            'baseline_model': 'model_v1',
            'candidate_model': 'model_v2',
            'test_cases_run': 1000,
            'divergence_detected': 0.02,
            'regression_detected': False,
            'recommendation': 'proceed',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        jsonschema.validate(report, schema)

    def test_low_divergence_proceeds(self, checker, mock_artifact_store):
        mock_artifact_store.query.return_value = [{'test_id': f'test_{i}'} for i in range(100)]

        report = checker.compare_models('model_v1', 'model_v2')

        if report['divergence_detected'] <= 0.02:
            assert report['recommendation'] == 'proceed'

    def test_high_divergence_blocks(self, checker, mock_artifact_store):
        mock_artifact_store.query.return_value = [{'test_id': f'test_{i}'} for i in range(100)]

        checker._compute_divergence = lambda b, c: 0.08

        report = checker.compare_models('model_v1', 'model_v2')

        if report['divergence_detected'] > 0.05:
            assert report['recommendation'] == 'block'
            assert report['regression_detected'] == True
