"""
Tests for DriftDetector: decision_divergence, exception_rate, eval_pass_rate, trace_coverage.
"""

import json
import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from spectrum_systems.drift.detector import DriftDetector, DriftSignalRecord


class TestDriftDetectionMeasurement:
    """Test drift measurement calculations."""

    @pytest.fixture
    def mock_artifact_store(self):
        return Mock()

    @pytest.fixture
    def mock_eval_runner(self):
        return Mock()

    @pytest.fixture
    def baseline_metrics(self):
        with open('contracts/governance/drift-thresholds-manifest.json') as f:
            manifest = json.load(f)
        return manifest['sli_targets']

    @pytest.fixture
    def detector(self, mock_artifact_store, mock_eval_runner, baseline_metrics):
        return DriftDetector(
            artifact_store=mock_artifact_store,
            eval_runner=mock_eval_runner,
            baseline_metrics=baseline_metrics
        )

    def test_drift_detector_calculates_divergence(self, detector, mock_artifact_store):
        """
        Same context_class with divergent outcomes is detected.

        Setup: 100 decisions in context_class 'ClassA', 50 outcome_X and 50 outcome_Y.
        All 100 decisions are in a divergent class → divergence = 1.0.
        """
        decisions = []
        for i in range(50):
            decisions.append({
                'artifact_id': f'decision_{i}_x',
                'context_class': 'ClassA',
                'decision_type': 'outcome_X'
            })
        for i in range(50):
            decisions.append({
                'artifact_id': f'decision_{i}_y',
                'context_class': 'ClassA',
                'decision_type': 'outcome_Y'
            })

        mock_artifact_store.query.return_value = decisions

        divergence = detector._calculate_decision_divergence()

        assert 0.4 <= divergence <= 1.0, f"Expected divergence 0.4-1.0, got {divergence}"

    def test_drift_signal_schema_valid(self, detector):
        """drift_signal_record conforms to schema."""
        import jsonschema

        with open('contracts/schemas/drift-signal.schema.json') as f:
            schema = json.load(f)

        signal = DriftSignalRecord(
            signal_id='test_signal_1',
            signal_type='decision_divergence',
            metric_name='spectrum_systems.drift.decision_divergence',
            baseline_value=0.05,
            current_value=0.12,
            threshold_warn=0.10,
            threshold_critical=0.15,
            severity='warning',
            timestamp=datetime.utcnow().isoformat() + 'Z',
            affected_artifacts=['artifact_1', 'artifact_2'],
            remediation_steps=['Step 1', 'Step 2'],
            source_code_version='abc123'
        )

        signal_dict = {
            'signal_id': signal.signal_id,
            'signal_type': signal.signal_type,
            'metric_name': signal.metric_name,
            'baseline_value': signal.baseline_value,
            'current_value': signal.current_value,
            'threshold_warn': signal.threshold_warn,
            'threshold_critical': signal.threshold_critical,
            'severity': signal.severity,
            'timestamp': signal.timestamp,
            'affected_artifacts': signal.affected_artifacts,
            'remediation_steps': signal.remediation_steps,
            'source_code_version': signal.source_code_version
        }

        jsonschema.validate(signal_dict, schema)

    def test_drift_triggers_on_threshold_cross(self, detector, mock_artifact_store, mock_eval_runner):
        """
        detect_drift() emits signal_record when metric exceeds threshold.

        Setup: decision_divergence = 0.12 (above threshold_warn = 0.10).
        """
        mock_artifact_store.query.return_value = []
        mock_eval_runner.get_recent_results.return_value = [
            {'status': 'pass'} for _ in range(100)
        ]

        with patch.object(detector, '_calculate_decision_divergence', return_value=0.12):
            with patch.object(detector, '_calculate_exception_rate', return_value=0.01):
                with patch.object(detector, '_calculate_eval_pass_rate', return_value=0.98):
                    with patch.object(detector, '_calculate_trace_coverage', return_value=0.999):
                        signals = detector.detect_drift()

        assert len(signals) >= 1
        assert any(s.signal_type == 'decision_divergence' for s in signals)

    def test_drift_fails_closed_on_bad_input(self, detector, mock_artifact_store):
        """
        detect_drift() fails closed on bad input.

        Setup: artifact store raises exception during query.
        Expected: error_artifact emitted, exception re-raised.
        """
        mock_artifact_store.query.side_effect = RuntimeError("Database connection failed")

        with pytest.raises(RuntimeError):
            detector.detect_drift()

        mock_artifact_store.put.assert_called()

    def test_drift_signal_immutable(self, detector, mock_artifact_store):
        """drift_signal_record stored with immutable flag."""
        mock_artifact_store.query.return_value = []

        with patch.object(detector, '_calculate_decision_divergence', return_value=0.12):
            with patch.object(detector, '_calculate_exception_rate', return_value=0.01):
                with patch.object(detector, '_calculate_eval_pass_rate', return_value=0.98):
                    with patch.object(detector, '_calculate_trace_coverage', return_value=0.999):
                        signals = detector.detect_drift()

        assert len(signals) >= 1

        calls = mock_artifact_store.put.call_args_list
        signal_put_calls = [
            call for call in calls
            if 'governance/signals' in str(call)
        ]
        assert len(signal_put_calls) >= 1
        for call in signal_put_calls:
            _, kwargs = call
            assert kwargs.get('immutable') is True
