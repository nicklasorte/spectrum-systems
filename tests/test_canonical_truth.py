"""Tests for canonical truth tracking."""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock
from spectrum_systems.governance.canonical_truth import CanonicalTruthManager


class TestCanonicalTruth:
    @pytest.fixture
    def mock_artifact_store(self):
        return Mock()

    @pytest.fixture
    def manager(self, mock_artifact_store):
        return CanonicalTruthManager(artifact_store=mock_artifact_store)

    def test_canonical_truth_schema_valid(self):
        import jsonschema
        with open('contracts/schemas/canonical-truth-manifest.schema.json') as f:
            schema = json.load(f)

        manifest = {
            'canonical_id': 'canon_policies',
            'canonical_version': '1.0.0',
            'canonical_data': {'policy_1': 'rule_1'},
            'hash': 'a' * 64,
            'created_timestamp': datetime.utcnow().isoformat() + 'Z',
            'last_verified_timestamp': datetime.utcnow().isoformat() + 'Z',
            'drift_detected': False
        }
        jsonschema.validate(manifest, schema)

    def test_canonical_truth_hashed_immutably(self, manager, mock_artifact_store):
        data = {'policy_a': 'rule_1', 'policy_b': 'rule_2'}
        record = manager.create_canonical_truth('canon_1', data, '1.0.0')

        assert record.hash is not None
        assert len(record.hash) == 64
        mock_artifact_store.put.assert_called()
        args, kwargs = mock_artifact_store.put.call_args
        assert kwargs.get('immutable') == True

    def test_drift_detection_changed_state(self, manager, mock_artifact_store):
        mock_artifact_store.query.return_value = [
            {'canonical_id': 'canon_1', 'hash': 'canonical_hash_value_' + '0' * 40}
        ]

        report = manager.verify_against_canonical('canon_1', {'policy_a': 'rule_2'})
        assert report['drift_detected'] == True
