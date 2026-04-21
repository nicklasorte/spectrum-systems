"""Tests for PolicyRegistry and hidden logic scanner."""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from spectrum_systems.governance.policy_registry import PolicyRegistry, PolicyRegistryEntry


class TestPolicyRegistry:
    """Test policy registration and ungoverned logic detection."""

    @pytest.fixture
    def mock_artifact_store(self):
        return Mock()

    @pytest.fixture
    def registry(self, mock_artifact_store):
        return PolicyRegistry(artifact_store=mock_artifact_store)

    def test_policy_entry_schema_valid(self):
        """Test: policy registry entry conforms to schema."""
        import jsonschema

        with open('contracts/schemas/policy-registry-entry.schema.json') as f:
            schema = json.load(f)

        entry = {
            'policy_id': 'test_policy',
            'policy_name': 'Test Policy',
            'policy_version': '1.0.0',
            'rule_id': 'rule_test_v1',
            'rule_condition_type': 'threshold',
            'rule_condition_text': 'eval_pass_rate > 0.95',
            'decision_class': 'promotion',
            'applies_to_artifact_types': ['eval_result'],
            'status': 'active',
            'created_timestamp': datetime.utcnow().isoformat() + 'Z',
            'source_code_version': 'abc123'
        }

        jsonschema.validate(entry, schema)

    def test_create_policy_immutably(self, registry, mock_artifact_store):
        """Test: policy stored with immutable flag."""
        policy_data = {
            'policy_name': 'Test Policy',
            'policy_version': '1.0.0',
            'rule_id': 'rule_test_v1',
            'rule_condition_type': 'threshold',
            'rule_condition_text': 'eval_pass_rate > 0.95',
            'decision_class': 'promotion',
            'applies_to_artifact_types': ['eval_result']
        }

        policy_id = registry.create_policy(policy_data)

        mock_artifact_store.put.assert_called_once()
        args, kwargs = mock_artifact_store.put.call_args
        assert kwargs.get('immutable') is True
        assert policy_id is not None

    def test_invalid_semver_rejected(self, registry):
        """Test: invalid semantic version rejected (fail-closed)."""
        policy_data = {
            'policy_name': 'Test',
            'policy_version': '1.0',
            'rule_id': 'rule_test_v1',
            'rule_condition_type': 'threshold',
            'rule_condition_text': 'x > 0.95',
            'decision_class': 'promotion',
            'applies_to_artifact_types': ['eval_result']
        }

        with pytest.raises(ValueError, match="semantic version"):
            registry.create_policy(policy_data)

    def test_missing_required_field_rejected(self, registry):
        """Test: missing required field rejected (fail-closed)."""
        policy_data = {
            'policy_name': 'Test',
            'policy_version': '1.0.0',
            'rule_id': 'rule_test_v1',
            'rule_condition_text': 'x > 0.95',
            'decision_class': 'promotion',
            'applies_to_artifact_types': ['eval_result']
        }

        with pytest.raises(ValueError, match="required field"):
            registry.create_policy(policy_data)

    def test_get_policy_by_id(self, registry, mock_artifact_store):
        """Test: retrieve policy by ID."""
        mock_artifact_store.query.return_value = [
            {
                'policy_id': 'test_policy',
                'status': 'active',
                'rule_condition_text': 'x > 0.95'
            }
        ]

        registry._load_policies()
        policy = registry.get_policy('test_policy')

        assert policy is not None
        assert policy['policy_id'] == 'test_policy'

    def test_get_policies_for_decision_class(self, registry, mock_artifact_store):
        """Test: retrieve all policies for decision class."""
        mock_artifact_store.query.return_value = [
            {
                'policy_id': 'policy_1',
                'decision_class': 'promotion',
                'status': 'active'
            },
            {
                'policy_id': 'policy_2',
                'decision_class': 'promotion',
                'status': 'active'
            },
            {
                'policy_id': 'policy_3',
                'decision_class': 'eval_block',
                'status': 'active'
            }
        ]

        registry._load_policies()
        policies = registry.get_policies_for_decision_class('promotion')

        assert len(policies) == 2
        assert all(p['decision_class'] == 'promotion' for p in policies)

    def test_audit_detects_hardcoded_thresholds(self, registry):
        """Test: ungoverned logic scanner detects hardcoded thresholds."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                stdout='spectrum_systems/control.py:42: if divergence > 0.10:\n',
                stderr=''
            )

            findings = registry.audit_for_hidden_logic()

            assert len(findings) > 0
            assert any(f['finding_type'] == 'hardcoded_threshold' for f in findings)

    def test_ungoverned_logic_audit_generates_artifact(self, registry, mock_artifact_store):
        """Test: audit generates immutable audit_artifact."""
        with patch.object(registry, 'audit_for_hidden_logic', return_value=[]):
            audit = registry.generate_ungoverned_logic_audit()

            assert audit['artifact_type'] == 'ungoverned_logic_audit'
            assert 'audit_id' in audit
            assert 'total_findings' in audit
            mock_artifact_store.put.assert_called()

    def test_policy_registry_fails_closed_on_error(self, registry, mock_artifact_store):
        """Test: policy registry emits error_artifact on load failure."""
        mock_artifact_store.query.side_effect = RuntimeError("DB error")

        with patch.object(registry, '_emit_error_artifact') as mock_emit:
            registry._load_policies()
            mock_emit.assert_called()

    def test_get_policy_fails_closed_returns_none(self, registry):
        """Test: get_policy returns None on error (fail-closed)."""
        registry.policies = None
        result = registry.get_policy('test_id')
        assert result is None

    def test_get_policies_for_class_fails_closed(self, registry):
        """Test: get_policies_for_decision_class returns [] on error."""
        registry.policies = None
        result = registry.get_policies_for_decision_class('promotion')
        assert result == []
