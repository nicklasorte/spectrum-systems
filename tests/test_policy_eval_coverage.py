"""Tests for policy eval coverage checking."""

import pytest
from datetime import datetime
from unittest.mock import Mock
from spectrum_systems.governance.policy_eval_coverage import PolicyEvalCoverageChecker


class TestPolicyEvalCoverage:
    @pytest.fixture
    def mock_artifact_store(self):
        return Mock()

    @pytest.fixture
    def checker(self, mock_artifact_store):
        return PolicyEvalCoverageChecker(artifact_store=mock_artifact_store)

    def test_coverage_report_generated(self, checker, mock_artifact_store):
        mock_artifact_store.query.side_effect = [
            [
                {'policy_id': 'policy_1', 'status': 'active'},
                {'policy_id': 'policy_2', 'status': 'active'},
            ],
            [{'eval_case_id': 'eval_1'}],
            [],
        ]

        report = checker.generate_coverage_report()

        assert report['total_policies'] == 2
        assert report['policies_with_evals'] == 1
        assert 'policy_2' in report['policies_without_evals']

    def test_full_coverage_allows_production(self, checker, mock_artifact_store):
        mock_artifact_store.query.side_effect = [
            [{'policy_id': 'policy_1'}],
            [{'eval_case_id': 'eval_1'}],
        ]

        report = checker.generate_coverage_report()
        assert report['coverage_percent'] == 100
        assert 'Proceed to production' in report['recommendation']
