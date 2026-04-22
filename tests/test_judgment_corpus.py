"""Tests for judgment corpus."""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock
from spectrum_systems.judgment.judgment_corpus import JudgmentCorpus


class TestJudgmentCorpus:
    @pytest.fixture
    def mock_artifact_store(self):
        return Mock()

    @pytest.fixture
    def corpus(self, mock_artifact_store):
        return JudgmentCorpus(artifact_store=mock_artifact_store)

    def test_judgment_schema_valid(self):
        import jsonschema
        with open('contracts/schemas/judgment-record.schema.json') as f:
            schema = json.load(f)

        judgment = {
            'judgment_id': 'judge_1',
            'decision_context': 'User requested high-risk action',
            'decision': 'require_additional_verification',
            'rationale': 'Risk exceeds threshold',
            'confidence': 0.95,
            'outcome_verified': False,
            'status': 'candidate',
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        jsonschema.validate(judgment, schema)

    def test_record_judgment(self, corpus, mock_artifact_store):
        judgment = corpus.record_judgment(
            'User risky action',
            'require_verification',
            'Risk > threshold',
            0.95
        )

        assert judgment['status'] == 'candidate'
        assert judgment['confidence'] == 0.95

    def test_query_precedents(self, corpus, mock_artifact_store):
        mock_artifact_store.query.return_value = [
            {
                'judgment_id': 'judge_1',
                'decision_context': 'User requested high-risk action',
                'decision': 'require_verification'
            }
        ]

        precedents = corpus.query_precedents('high-risk action')
        assert len(precedents) == 1

    def test_supersede_judgment(self, corpus, mock_artifact_store):
        supersession = corpus.supersede_judgment('judge_1', 'judge_2')
        assert supersession['superseded_judgment_id'] == 'judge_1'
        assert supersession['new_judgment_id'] == 'judge_2'
