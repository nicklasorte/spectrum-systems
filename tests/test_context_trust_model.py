"""Tests for context trust model."""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock
from spectrum_systems.trust.context_trust_model import ContextTrustModel


class TestContextTrustModel:
    @pytest.fixture
    def mock_artifact_store(self):
        return Mock()

    @pytest.fixture
    def model(self, mock_artifact_store):
        return ContextTrustModel(artifact_store=mock_artifact_store)

    def test_context_trust_schema_valid(self):
        import jsonschema
        with open('contracts/schemas/context-trust-score.schema.json') as f:
            schema = json.load(f)

        score = {
            'context_id': 'ctx_1',
            'source': 'user_input',
            'freshness_score': 0.95,
            'accuracy_score': 0.90,
            'completeness_score': 0.85,
            'overall_trust_score': 0.90,
            'admission_decision': 'admit',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        jsonschema.validate(score, schema)

    def test_high_trust_admitted(self, model, mock_artifact_store):
        context = {
            'context_id': 'ctx_1',
            'source': 'verified_api',
            'created_at': datetime.utcnow().isoformat() + 'Z',
            'data': {'key': 'value'}
        }

        score = model.score_context(context)
        assert score['overall_trust_score'] >= 0.7
        assert score['admission_decision'] in ['admit', 'quarantine']

    def test_low_trust_rejected(self, model, mock_artifact_store):
        context = {
            'context_id': 'ctx_1',
            'source': 'untrusted_source',
            'created_at': None,
            'data': None
        }

        score = model.score_context(context)
        assert score['overall_trust_score'] < 0.7
        assert score['admission_decision'] == 'reject'
