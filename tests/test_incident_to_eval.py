"""Tests for incident-to-eval conversion."""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock
from spectrum_systems.learning.incident_to_eval import IncidentToEvalConverter


class TestIncidentToEval:
    @pytest.fixture
    def mock_artifact_store(self):
        return Mock()

    @pytest.fixture
    def converter(self, mock_artifact_store):
        return IncidentToEvalConverter(artifact_store=mock_artifact_store)

    def test_postmortem_schema_valid(self):
        import jsonschema
        with open('contracts/schemas/postmortem-artifact.schema.json') as f:
            schema = json.load(f)

        postmortem = {
            'postmortem_id': 'pm_1',
            'incident_id': 'inc_1',
            'incident_type': 'eval_miss',
            'root_causes': ['Coverage gap'],
            'failure_pattern': 'eval_miss on long contexts > 5000 tokens',
            'eval_expansion_required': True,
            'proposed_eval_cases': [],
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'author': 'alice@example.com'
        }
        jsonschema.validate(postmortem, schema)

    def test_eval_proposal_generated(self, converter, mock_artifact_store):
        postmortem = {
            'postmortem_id': 'pm_1',
            'incident_id': 'inc_1',
            'incident_type': 'eval_miss',
            'root_causes': ['Gap'],
            'failure_pattern': 'eval_miss on long contexts > 5000 tokens',
            'eval_expansion_required': True,
            'proposed_eval_cases': []
        }

        proposals = converter.process_postmortem(postmortem)
        assert len(proposals) > 0
        assert proposals[0].is_critical == True
