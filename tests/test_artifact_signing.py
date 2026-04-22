"""Tests for SLSA provenance signing."""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock
from spectrum_systems.security.artifact_signing import ArtifactSigner


class TestArtifactSigning:
    @pytest.fixture
    def mock_artifact_store(self):
        return Mock()

    @pytest.fixture
    def signer(self, mock_artifact_store):
        return ArtifactSigner(artifact_store=mock_artifact_store, signer_id='signer_alice')

    def test_signed_provenance_schema_valid(self):
        import jsonschema
        with open('contracts/schemas/signed-provenance.schema.json') as f:
            schema = json.load(f)

        provenance = {
            'artifact_id': 'artifact_1',
            'artifact_hash': 'a' * 64,
            'provenance_statement': {'builder': {'id': 'spectrum_systems_v1'}, 'materials': {'artifact_id': 'artifact_1'}},
            'signature': 'sig_base64_encoded_' + 'x' * 100,
            'signer_id': 'signer_alice',
            'signature_algorithm': 'RSA-SHA256',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'slsa_level': 2
        }
        jsonschema.validate(provenance, schema)

    def test_high_severity_artifact_signed(self, signer, mock_artifact_store):
        artifact = {'artifact_id': 'critical_artifact', 'artifact_type': 'control_decision', 'severity': 'high', 'data': {'decision': 'block'}}
        record = signer.sign_artifact(artifact, severity='high')

        assert record is not None
        assert record.artifact_id == 'critical_artifact'
        assert record.slsa_level == 2

    def test_low_severity_artifact_not_signed(self, signer, mock_artifact_store):
        artifact = {'artifact_id': 'low_artifact', 'artifact_type': 'log_entry', 'severity': 'low'}
        record = signer.sign_artifact(artifact, severity='low')
        assert record is None
