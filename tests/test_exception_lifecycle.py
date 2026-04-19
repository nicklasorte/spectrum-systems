"""
Tests for ExceptionLifecycleManager: tracking, expiry, policy generation.
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock
from spectrum_systems.exceptions.lifecycle_manager import ExceptionLifecycleManager, ExceptionArtifact


class TestExceptionLifecycle:
    """Test exception tracking and lifecycle."""

    @pytest.fixture
    def mock_artifact_store(self):
        return Mock()

    @pytest.fixture
    def lifecycle_manager(self, mock_artifact_store):
        return ExceptionLifecycleManager(artifact_store=mock_artifact_store)

    def test_exception_artifact_schema_valid(self):
        """exception_artifact conforms to schema."""
        import jsonschema

        with open('contracts/schemas/exception-artifact.schema.json') as f:
            schema = json.load(f)

        tomorrow = (datetime.utcnow() + timedelta(days=1)).isoformat() + 'Z'

        exception = {
            'exception_id': 'exc_1',
            'exception_reason': 'Emergency hotfix needed for production outage',
            'issued_by': 'alice@example.com',
            'issued_date': datetime.utcnow().isoformat() + 'Z',
            'expiry_date': tomorrow,
            'affected_resource': 'promotion_readiness_gate',
            'severity': 'high',
            'policy_candidate_generated': False,
            'conversion_status': 'pending',
            'created_timestamp': datetime.utcnow().isoformat() + 'Z'
        }

        jsonschema.validate(exception, schema)

    def test_exception_immutability(self, lifecycle_manager, mock_artifact_store):
        """exception_artifact stored with immutable flag."""
        tomorrow = (datetime.utcnow() + timedelta(days=1)).isoformat() + 'Z'

        exception_data = {
            'exception_reason': 'Test exception',
            'issued_by': 'user@example.com',
            'expiry_date': tomorrow,
            'affected_resource': 'test_gate',
            'severity': 'low'
        }

        exc_id = lifecycle_manager.track_exception(exception_data)

        mock_artifact_store.put.assert_called_once()
        _, kwargs = mock_artifact_store.put.call_args
        assert kwargs.get('immutable') is True
        assert exc_id is not None

    def test_exception_expiry_trigger(self, lifecycle_manager, mock_artifact_store):
        """check_expiry() marks exceptions as expired."""
        now = datetime.utcnow()
        yesterday = (now - timedelta(days=1)).isoformat() + 'Z'

        mock_artifact_store.query.return_value = [
            {
                'exception_id': 'exc_1',
                'expiry_date': yesterday,
                'conversion_status': 'pending',
                'affected_resource': 'gate_A',
                'issued_date': (now - timedelta(days=2)).isoformat() + 'Z'
            }
        ]

        lifecycle_manager.check_expiry()

        mock_artifact_store.update_field.assert_called()

    def test_policy_candidate_generation(self, lifecycle_manager, mock_artifact_store):
        """5+ exceptions of same resource type trigger policy_candidate generation."""
        now = datetime.utcnow()
        future = (now + timedelta(days=30)).isoformat() + 'Z'

        exceptions = []
        for i in range(5):
            exceptions.append({
                'exception_id': f'exc_{i}',
                'exception_reason': 'Time pressure',
                'expiry_date': future,
                'conversion_status': 'pending',
                'affected_resource': 'eval_coverage_gate',
                'issued_date': (now - timedelta(days=10 + i)).isoformat() + 'Z'
            })

        mock_artifact_store.query.return_value = exceptions

        candidates = lifecycle_manager.check_expiry()

        put_calls = [
            call for call in mock_artifact_store.put.call_args_list
            if 'governance/policies/candidates' in str(call)
        ]
        assert len(put_calls) >= 1

    def test_exception_attribution(self, lifecycle_manager, mock_artifact_store):
        """Exception attribution recorded immutably."""
        tomorrow = (datetime.utcnow() + timedelta(days=1)).isoformat() + 'Z'

        exception_data = {
            'exception_reason': 'Test',
            'issued_by': 'alice@example.com',
            'expiry_date': tomorrow,
            'affected_resource': 'gate',
            'severity': 'low'
        }

        lifecycle_manager.track_exception(exception_data)

        args, _ = mock_artifact_store.put.call_args
        exception_artifact = args[0]
        assert exception_artifact['issued_by'] == 'alice@example.com'

    def test_exception_no_indefinite_expiry(self, lifecycle_manager):
        """Exceptions cannot be created without expiry_date (fail-closed)."""
        exception_data = {
            'exception_reason': 'Test',
            'issued_by': 'user@example.com',
            'affected_resource': 'gate',
            'severity': 'low'
        }

        with pytest.raises(ValueError, match="no indefinite exceptions"):
            lifecycle_manager.track_exception(exception_data)

    def test_exception_expiry_in_past_blocked(self, lifecycle_manager):
        """expiry_date in past is rejected (fail-closed)."""
        yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat() + 'Z'

        exception_data = {
            'exception_reason': 'Test',
            'issued_by': 'user@example.com',
            'expiry_date': yesterday,
            'affected_resource': 'gate',
            'severity': 'low'
        }

        with pytest.raises(ValueError, match="must be in future"):
            lifecycle_manager.track_exception(exception_data)

    def test_exception_hotspot_detection(self, lifecycle_manager, mock_artifact_store):
        """get_exception_hotspots() returns gates by exception frequency."""
        mock_artifact_store.query.return_value = [
            {'affected_resource': 'gate_A'},
            {'affected_resource': 'gate_A'},
            {'affected_resource': 'gate_A'},
            {'affected_resource': 'gate_B'},
            {'affected_resource': 'gate_B'},
            {'affected_resource': 'gate_C'},
        ]

        hotspots = lifecycle_manager.get_exception_hotspots(days=30)

        assert hotspots['gate_A'] == 3
        assert hotspots['gate_B'] == 2
        assert hotspots['gate_C'] == 1
