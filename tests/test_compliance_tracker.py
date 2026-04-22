"""Tests for compliance tracking."""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock
from spectrum_systems.governance.compliance_tracker import ComplianceTracker


class TestComplianceTracker:
    @pytest.fixture
    def mock_artifact_store(self):
        return Mock()

    @pytest.fixture
    def tracker(self, mock_artifact_store):
        return ComplianceTracker(artifact_store=mock_artifact_store)

    def test_compliance_schema_valid(self):
        import jsonschema
        with open('contracts/schemas/compliance-status-report.schema.json') as f:
            schema = json.load(f)

        report = {
            'report_id': 'report_1',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'total_policies': 100,
            'policies_compliant': 100,
            'compliance_percent': 100,
            'sla_metrics': {'production_ready': True},
            'audit_status': 'pass',
            'recommendation': 'Ready for production'
        }
        jsonschema.validate(report, schema)

    def test_full_compliance_passes_audit(self, tracker, mock_artifact_store):
        mock_artifact_store.query.return_value = [
            {
                'policy_id': 'p_1',
                'version': '1.0.0',
                'status': 'active',
                'eval_backing': 'eval_1'
            }
        ]

        report = tracker.generate_compliance_report()

        assert report['compliance_percent'] == 100
        assert report['audit_status'] == 'pass'

    def test_incomplete_compliance_blocks_audit(self, tracker, mock_artifact_store):
        mock_artifact_store.query.return_value = [
            {
                'policy_id': 'p_1',
                'version': '1.0.0',
                'status': 'active'
            }
        ]

        report = tracker.generate_compliance_report()

        assert report['compliance_percent'] < 100
        assert report['audit_status'] in ['warning', 'fail']
