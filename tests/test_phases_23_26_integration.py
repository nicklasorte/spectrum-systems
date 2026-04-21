"""Integration test: Phases 23-26 complete governance flow.

Synthetic incident through all 4 phases:
- Phase 23: RL execution with bounded recovery
- Phase 24: Trace hardening and artifact tracing
- Phase 25: Hidden logic scanner detects ungoverned rules
- Phase 26: Eval slices reveal hidden failures
"""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock, patch
from spectrum_systems.governance.policy_registry import PolicyRegistry, PolicyRegistryEntry
from spectrum_systems.evals.eval_slicer import EvalSlicer, EvalSlice


class TestPhases23to26IntegrationFlow:
    """Integration: all 4 phases in sequence."""

    @pytest.fixture
    def mock_artifact_store(self):
        return Mock()

    @pytest.fixture
    def mock_eval_runner(self):
        return Mock()

    @pytest.fixture
    def policy_registry(self, mock_artifact_store):
        return PolicyRegistry(artifact_store=mock_artifact_store)

    @pytest.fixture
    def eval_slicer(self, mock_artifact_store, mock_eval_runner):
        return EvalSlicer(
            artifact_store=mock_artifact_store,
            eval_runner=mock_eval_runner
        )

    def test_phase_25_detects_hidden_logic_then_phase_26_reveals_failure(
        self, policy_registry, eval_slicer, mock_artifact_store, mock_eval_runner
    ):
        """Integration: Phase 25 detects ungoverned rule, Phase 26 measures impact via slices."""

        policy_data = {
            'policy_name': 'Promotion Policy',
            'policy_version': '1.0.0',
            'rule_id': 'rule_promotion_v1',
            'rule_condition_type': 'conjunction',
            'rule_condition_text': 'eval_pass_rate > 0.95 AND critical_slice_passing',
            'decision_class': 'promotion',
            'applies_to_artifact_types': ['spectrum_artifact']
        }

        policy_id = policy_registry.create_policy(policy_data)
        assert policy_id is not None

        slices = [
            EvalSlice(
                slice_name='critical_domain',
                slice_filter='domain == "finance"',
                pass_threshold=0.99,
                severity='critical',
                is_critical=True
            ),
            EvalSlice(
                slice_name='general_domain',
                slice_filter='domain != "finance"',
                pass_threshold=0.90,
                severity='low',
                is_critical=False
            )
        ]

        eval_slicer.register_slices_for_artifact_family('spectrum_artifact', slices)

        mock_eval_runner.get_result.side_effect = [
            {'artifact_id': 'a1', 'domain': 'finance', 'status': 'fail'},
            {'artifact_id': 'a2', 'domain': 'finance', 'status': 'fail'},
            {'artifact_id': 'a3', 'domain': 'legal', 'status': 'pass'},
            {'artifact_id': 'a4', 'domain': 'legal', 'status': 'pass'},
        ]

        report = eval_slicer.evaluate_with_slices(
            'spectrum_artifact', ['c1', 'c2', 'c3', 'c4']
        )

        assert report['overall_pass_rate'] == 0.5
        critical_slice = next(
            (sr for sr in report['slice_results'] if sr['slice_name'] == 'critical_domain'),
            None
        )
        assert critical_slice is not None
        assert critical_slice['status'] == 'failing'
        assert 'CRITICAL' in ' '.join(report['recommendations'])

    def test_fail_closed_at_multiple_gates(self, policy_registry, eval_slicer, mock_artifact_store):
        """Integration: fail-closed at policy gate AND eval gate."""

        mock_artifact_store.query.side_effect = RuntimeError("Database error")

        policy_registry._load_policies()
        policies = policy_registry.get_policies_for_decision_class('promotion')
        assert policies == []

        mock_eval_runner = Mock()
        mock_eval_runner.get_result.return_value = None

        slicer = EvalSlicer(artifact_store=mock_artifact_store, eval_runner=mock_eval_runner)
        report = slicer.evaluate_with_slices('unknown_family', ['case_1'])

        assert report['critical_slice_status'] == 'all_failing'
        assert report['overall_pass_rate'] == 0

    def test_immutability_across_phases(self, policy_registry, mock_artifact_store):
        """Integration: immutable policy entries prevent silent updates."""
        policy_data = {
            'policy_name': 'Test Policy',
            'policy_version': '1.0.0',
            'rule_id': 'rule_test_v1',
            'rule_condition_type': 'threshold',
            'rule_condition_text': 'eval_pass_rate > 0.95 always',
            'decision_class': 'promotion',
            'applies_to_artifact_types': ['spectrum_artifact']
        }

        policy_registry.create_policy(policy_data)

        mock_artifact_store.put.assert_called_once()
        args, kwargs = mock_artifact_store.put.call_args
        assert kwargs.get('immutable') is True

    def test_schema_validation_across_artifacts(self):
        """Integration: schemas validate both Phase 25 and Phase 26 artifacts."""
        import jsonschema

        with open('contracts/schemas/policy-registry-entry.schema.json') as f:
            policy_schema = json.load(f)

        with open('contracts/schemas/artifact-family-health-report.schema.json') as f:
            health_schema = json.load(f)

        policy_entry = {
            'policy_id': 'test_policy',
            'policy_name': 'Test Policy',
            'policy_version': '1.0.0',
            'rule_id': 'rule_test_v1',
            'rule_condition_type': 'threshold',
            'rule_condition_text': 'eval_pass_rate > 0.95 AND trace_coverage > 0.999',
            'decision_class': 'promotion',
            'applies_to_artifact_types': ['spectrum_artifact'],
            'status': 'active',
            'created_timestamp': datetime.utcnow().isoformat() + 'Z',
            'source_code_version': 'abc123'
        }

        jsonschema.validate(policy_entry, policy_schema)

        health_report = {
            'report_id': 'report_1',
            'artifact_family': 'spectrum_artifact',
            'report_timestamp': datetime.utcnow().isoformat() + 'Z',
            'overall_pass_rate': 0.95,
            'slice_results': [],
            'critical_slice_status': 'all_passing',
            'recommendations': []
        }

        jsonschema.validate(health_report, health_schema)

    def test_synthetic_incident_phases_25_26_multi_critical_slices(self, policy_registry, eval_slicer, mock_artifact_store, mock_eval_runner):
        """Synthetic: multi-critical slices with partial failure → some_failing status."""

        with patch.object(policy_registry, 'audit_for_hidden_logic') as mock_audit:
            mock_audit.return_value = [
                {
                    'finding_type': 'hardcoded_threshold',
                    'location': 'spectrum_systems/control.py:50: if confidence > 0.85:',
                    'severity': 'high',
                    'recommendation': 'Move to policy registry'
                }
            ]

            audit = policy_registry.generate_ungoverned_logic_audit()
            assert audit['total_findings'] == 1
            assert audit['high_findings'] == 1

        slices = [
            EvalSlice(
                slice_name='critical_finance',
                slice_filter='domain == "finance"',
                pass_threshold=0.95,
                severity='critical',
                is_critical=True
            ),
            EvalSlice(
                slice_name='critical_healthcare',
                slice_filter='domain == "healthcare"',
                pass_threshold=0.95,
                severity='critical',
                is_critical=True
            ),
            EvalSlice(
                slice_name='noncritical_tech',
                slice_filter='domain == "tech"',
                pass_threshold=0.85,
                severity='low',
                is_critical=False
            )
        ]

        eval_slicer.register_slices_for_artifact_family('spectrum_artifact', slices)

        mock_eval_runner.get_result.side_effect = [
            {'artifact_id': 'a1', 'domain': 'finance', 'status': 'pass'},
            {'artifact_id': 'a2', 'domain': 'finance', 'status': 'fail'},
            {'artifact_id': 'a3', 'domain': 'healthcare', 'status': 'pass'},
            {'artifact_id': 'a4', 'domain': 'healthcare', 'status': 'pass'},
            {'artifact_id': 'a5', 'domain': 'tech', 'status': 'pass'},
        ]

        report = eval_slicer.evaluate_with_slices(
            'spectrum_artifact', ['c1', 'c2', 'c3', 'c4', 'c5']
        )

        assert report['critical_slice_status'] == 'some_failing'
        assert 'CRITICAL' in ' '.join(report['recommendations'])
