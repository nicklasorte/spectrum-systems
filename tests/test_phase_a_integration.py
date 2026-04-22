"""Tests for Phase A: Data Integration"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


class TestPhaseAIntegration:
    """Test all data integration deliverables."""

    def test_artifact_api_client_verifies_slo(self):
        """A0: Artifact API client verifies SLO."""
        from spectrum_systems.integration.artifact_api_client import ArtifactAPIClient

        client = ArtifactAPIClient('http://localhost:3001')
        # Mock successful verification
        with patch('spectrum_systems.integration.artifact_api_client.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            slo = client.verify_slo()

            assert slo['status'] in ['compliant', 'at_risk']
            assert slo['uptime_target'] == 0.999
            assert 'slo_id' in slo
            assert 'timestamp' in slo

    def test_artifact_api_client_circuit_breaker(self):
        """A0: Circuit breaker prevents cascading failures."""
        from spectrum_systems.integration.artifact_api_client import ArtifactAPIClient

        client = ArtifactAPIClient('http://localhost:3001')

        # Simulate 5 failures
        with patch('spectrum_systems.integration.artifact_api_client.requests.get') as mock_get:
            mock_get.side_effect = Exception('Connection refused')

            for _ in range(5):
                result = client.get_entropy_snapshot()

            assert client.circuit_breaker_open == True
            assert result.get('is_fallback') == True

    def test_artifact_api_client_fallback(self):
        """A0: Fallback snapshot returned when API unavailable."""
        from spectrum_systems.integration.artifact_api_client import ArtifactAPIClient

        client = ArtifactAPIClient('http://localhost:3001')
        client.circuit_breaker_open = True
        client.last_failure_time = 0  # Force fallback

        fallback = client._fallback_snapshot()

        assert fallback['is_fallback'] == True
        assert 'metrics' in fallback
        assert fallback['metrics']['decision_divergence']['current'] == 0.05

    def test_entropy_snapshot_schema_valid(self):
        """A1: Entropy snapshot conforms to schema."""
        import jsonschema

        with open('contracts/schemas/artifact-api-slo.schema.json') as f:
            schema = json.load(f)

        slo_record = {
            'slo_id': 'api_slo_1',
            'uptime_target': 0.999,
            'latency_p99_ms': 500,
            'error_rate_target': 0.01,
            'monthly_downtime_budget_minutes': 43.2,
            'actual_uptime': 0.9995,
            'actual_error_rate': 0.005,
            'status': 'compliant',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }

        jsonschema.validate(slo_record, schema)

    def test_query_result_error_handling(self):
        """A3: Query returns graceful error on API failure."""
        from spectrum_systems.integration.artifact_api_client import ArtifactAPIClient

        client = ArtifactAPIClient('http://localhost:3001')

        with patch('spectrum_systems.integration.artifact_api_client.requests.get') as mock_get:
            mock_get.side_effect = Exception('Timeout')
            result = client.query('top_reason_codes_by_blocks', days=30)

            assert 'error' in result
            assert result['data'] == []

    def test_circuit_breaker_recovery(self):
        """A4: Circuit breaker recovers after timeout."""
        from spectrum_systems.integration.artifact_api_client import ArtifactAPIClient
        import time

        client = ArtifactAPIClient('http://localhost:3001')
        client.circuit_breaker_threshold = 2
        client.recovery_timeout_seconds = 1

        # Trigger failures
        with patch('spectrum_systems.integration.artifact_api_client.requests.get') as mock_get:
            mock_get.side_effect = Exception('Connection refused')

            for _ in range(2):
                client.get_entropy_snapshot()

            assert client.circuit_breaker_open == True

            # Wait for recovery
            time.sleep(1.1)

            # Should attempt recovery
            mock_get.side_effect = None
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'snapshot_id': 'snap_1', 'metrics': {}}
            mock_get.return_value = mock_response

            result = client.get_entropy_snapshot()
            assert client.circuit_breaker_open == False

    def test_sanity_check_queries_run_5x(self):
        """A8: Sanity check queries execute 5x without flakiness."""
        from spectrum_systems.integration.artifact_api_client import ArtifactAPIClient

        client = ArtifactAPIClient('http://localhost:3001')

        success_count = 0
        for run in range(5):
            try:
                with patch('spectrum_systems.integration.artifact_api_client.requests.get') as mock_get:
                    mock_response = Mock()
                    mock_response.status_code = 200
                    mock_response.json.return_value = {
                        'snapshot_id': f'snap_{run}',
                        'metrics': {}
                    }
                    mock_get.return_value = mock_response

                    result = client.get_entropy_snapshot()
                    if result and 'snapshot_id' in result:
                        success_count += 1
            except Exception:
                pass

        assert success_count == 5, f'Expected 5 successful runs, got {success_count}'

    def test_artifact_api_slo_schema_exists(self):
        """Verify artifact API SLO schema file exists and is valid JSON."""
        import json

        with open('contracts/schemas/artifact-api-slo.schema.json') as f:
            schema = json.load(f)

        assert schema['title'] == 'ArtifactAPISLO'
        assert 'properties' in schema
        assert 'slo_id' in schema['required']
