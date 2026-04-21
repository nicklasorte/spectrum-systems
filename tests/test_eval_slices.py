"""Tests for EvalSlicer: multi-dimensional rubrics, slice-based evaluation."""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock, patch
from spectrum_systems.evals.eval_slicer import EvalSlicer, EvalSlice, SliceResult


class TestEvalSlices:
    """Test slice-based evaluation."""

    @pytest.fixture
    def mock_artifact_store(self):
        return Mock()

    @pytest.fixture
    def mock_eval_runner(self):
        return Mock()

    @pytest.fixture
    def slicer(self, mock_artifact_store, mock_eval_runner):
        return EvalSlicer(
            artifact_store=mock_artifact_store,
            eval_runner=mock_eval_runner
        )

    def test_artifact_family_health_report_schema_valid(self):
        """Test: health report conforms to schema."""
        import jsonschema

        with open('contracts/schemas/artifact-family-health-report.schema.json') as f:
            schema = json.load(f)

        report = {
            'report_id': 'report_1',
            'artifact_family': 'spectrum_artifact',
            'report_timestamp': datetime.utcnow().isoformat() + 'Z',
            'overall_pass_rate': 0.95,
            'slice_results': [
                {
                    'slice_name': 'long_context',
                    'slice_filter': 'context_length > 5000',
                    'pass_rate': 0.92,
                    'sample_count': 100,
                    'severity': 'high',
                    'status': 'passing'
                }
            ],
            'critical_slice_status': 'all_passing',
            'recommendations': []
        }

        jsonschema.validate(report, schema)

    def test_register_slices_for_artifact_family(self, slicer, mock_artifact_store):
        """Test: slices registered and stored immutably."""
        slices = [
            EvalSlice(
                slice_name='long_context',
                slice_filter='context_length > 5000',
                pass_threshold=0.95,
                severity='high',
                is_critical=False
            ),
            EvalSlice(
                slice_name='critical_domain',
                slice_filter='domain == "finance"',
                pass_threshold=0.99,
                severity='critical',
                is_critical=True
            )
        ]

        slicer.register_slices_for_artifact_family('spectrum_artifact', slices)

        assert 'spectrum_artifact' in slicer.slices
        assert len(slicer.slices['spectrum_artifact']) == 2
        mock_artifact_store.put.assert_called()
        args, kwargs = mock_artifact_store.put.call_args
        assert kwargs.get('immutable') is True

    def test_slice_filtering_by_predicate(self, slicer):
        """Test: predicate-based filtering works."""
        results = [
            {'artifact_id': 'a1', 'context_length': 6000, 'status': 'pass'},
            {'artifact_id': 'a2', 'context_length': 3000, 'status': 'pass'},
            {'artifact_id': 'a3', 'context_length': 7000, 'status': 'fail'},
        ]

        filtered = slicer._filter_by_predicate(results, 'context_length > 5000')

        assert len(filtered) == 2
        assert all(r['context_length'] > 5000 for r in filtered)

    def test_critical_slice_failure_blocks_promotion(self, slicer, mock_artifact_store, mock_eval_runner):
        """Test: critical slice failure triggers block recommendation."""
        mock_eval_runner.get_result.side_effect = [
            {'artifact_id': 'a1', 'domain': 'finance', 'status': 'pass'},
            {'artifact_id': 'a2', 'domain': 'finance', 'status': 'fail'},
            {'artifact_id': 'a3', 'domain': 'finance', 'status': 'fail'},
        ]

        slices = [
            EvalSlice(
                slice_name='critical_finance',
                slice_filter='domain == "finance"',
                pass_threshold=0.95,
                severity='critical',
                is_critical=True
            )
        ]

        slicer.register_slices_for_artifact_family('spectrum_artifact', slices)
        slicer.slices['spectrum_artifact'] = slices

        report = slicer.evaluate_with_slices('spectrum_artifact', ['case_1', 'case_2', 'case_3'])

        assert 'CRITICAL' in ' '.join(report['recommendations'])
        assert report['critical_slice_status'] != 'all_passing'

    def test_eval_slices_fail_closed_on_error(self, slicer, mock_artifact_store, mock_eval_runner):
        """Test: eval slicer fails closed on error."""
        mock_eval_runner.get_result.side_effect = RuntimeError("Eval failed")

        report = slicer.evaluate_with_slices('spectrum_artifact', ['case_1'])

        assert report['overall_pass_rate'] == 0
        assert 'ERROR' in ' '.join(report['recommendations'])

    def test_insufficient_slice_samples_marked_warning(self, slicer, mock_artifact_store, mock_eval_runner):
        """Test: slice with no samples marked as warning."""
        mock_eval_runner.get_result.side_effect = [
            {'artifact_id': 'a1', 'domain': 'legal', 'status': 'pass'},
        ]

        slices = [
            EvalSlice(
                slice_name='finance_only',
                slice_filter='domain == "finance"',
                pass_threshold=0.95,
                severity='high',
                is_critical=False
            )
        ]

        slicer.register_slices_for_artifact_family('spectrum_artifact', slices)
        slicer.slices['spectrum_artifact'] = slices

        report = slicer.evaluate_with_slices('spectrum_artifact', ['case_1'])

        finance_slice = next((sr for sr in report['slice_results'] if sr['slice_name'] == 'finance_only'), None)
        assert finance_slice is not None
        assert finance_slice['status'] == 'warning'

    def test_evaluate_with_slices_no_results_returns_error(self, slicer, mock_eval_runner):
        """Test: no eval results returns error_artifact."""
        mock_eval_runner.get_result.return_value = None

        report = slicer.evaluate_with_slices('spectrum_artifact', ['case_1'])

        assert report['critical_slice_status'] == 'all_failing'
        assert 'ERROR' in ' '.join(report['recommendations'])

    def test_evaluate_with_slices_no_registered_slices_returns_error(self, slicer, mock_eval_runner):
        """Test: no registered slices returns error_artifact."""
        mock_eval_runner.get_result.return_value = {'artifact_id': 'a1', 'status': 'pass'}
        slicer.slices = {}

        report = slicer.evaluate_with_slices('unknown_family', ['case_1'])

        assert report['critical_slice_status'] == 'all_failing'
        assert 'ERROR' in ' '.join(report['recommendations'])
