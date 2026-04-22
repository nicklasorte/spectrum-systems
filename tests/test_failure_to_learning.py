"""Tests for failure-to-learning pipeline."""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock
from spectrum_systems.learning.failure_to_learning import FailureToLearningPipeline


class TestFailureToLearning:
    @pytest.fixture
    def mock_artifact_store(self):
        return Mock()

    @pytest.fixture
    def pipeline(self, mock_artifact_store):
        return FailureToLearningPipeline(artifact_store=mock_artifact_store)

    def test_failure_learning_schema_valid(self):
        import jsonschema
        with open('contracts/schemas/failure-learning-record.schema.json') as f:
            schema = json.load(f)

        record = {
            'learning_id': 'learn_1',
            'incident_id': 'inc_1',
            'failure_type': 'eval_miss',
            'root_cause': 'Missing eval case for long contexts',
            'learning_action': 'eval_expansion',
            'status': 'proposed',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        jsonschema.validate(record, schema)

    def test_eval_miss_triggers_eval_expansion(self, pipeline, mock_artifact_store):
        incident = {
            'incident_id': 'inc_1',
            'incident_type': 'eval_miss',
            'root_cause': 'Missing eval'
        }

        learning = pipeline.process_incident_to_learning(incident)

        assert learning['learning_action'] == 'eval_expansion'
        assert learning['status'] == 'proposed'

    def test_decision_error_triggers_policy_update(self, pipeline, mock_artifact_store):
        incident = {
            'incident_id': 'inc_1',
            'incident_type': 'decision_error',
            'root_cause': 'Policy error'
        }

        learning = pipeline.process_incident_to_learning(incident)

        assert learning['learning_action'] == 'policy_update'

    def test_verify_all_failures_learned(self, pipeline, mock_artifact_store):
        mock_artifact_store.query.side_effect = [
            [{'incident_id': 'inc_1'}, {'incident_id': 'inc_2'}],
            [{'incident_id': 'inc_1', 'learning_action': 'eval_expansion'}]
        ]

        report = pipeline.verify_all_failures_learned()

        assert report['total_incidents'] == 2
        assert report['learned_incidents'] == 1
        assert 'inc_2' in report['unlearned_incidents']
