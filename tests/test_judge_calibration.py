"""
Tests for JudgeCalibrationTracker: calibration, disagreement, trust scoring.
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from spectrum_systems.governance.judge_calibration import JudgeCalibrationTracker, CalibrationRecord


class TestJudgeCalibration:
    """Test judge calibration tracking."""

    @pytest.fixture
    def mock_artifact_store(self):
        return Mock()

    @pytest.fixture
    def mock_eval_runner(self):
        return Mock()

    @pytest.fixture
    def tracker(self, mock_artifact_store, mock_eval_runner):
        return JudgeCalibrationTracker(
            artifact_store=mock_artifact_store,
            eval_runner=mock_eval_runner
        )

    def test_calibration_record_schema_valid(self):
        """Test: calibration record conforms to schema."""
        from spectrum_systems.contracts.schemas import JUDGE_CALIBRATION_RECORD_SCHEMA
        try:
            import jsonschema
        except ImportError:
            pytest.skip("jsonschema not installed")

        record = {
            'calibration_id': 'cal_1',
            'judge_id': 'judge_a',
            'confidence_bucket': '0.9-0.95',
            'total_decisions': 100,
            'correct_decisions': 90,
            'actual_accuracy': 0.90,
            'expected_accuracy': 0.925,
            'calibration_error': 0.025,
            'is_miscalibrated': False,
            'measurement_period': 'weekly',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'source_code_version': 'abc123'
        }

        jsonschema.validate(record, JUDGE_CALIBRATION_RECORD_SCHEMA)

    def test_overconfident_judge_detected(self, tracker, mock_artifact_store):
        """Test: overconfident judge flagged (expected > actual)."""
        mock_artifact_store.query.return_value = [
            {'decision_id': f'd_{i}', 'confidence': 0.92, 'ground_truth_correct': i < 85}
            for i in range(100)
        ]

        records = tracker.measure_calibration('judge_a', 'weekly')

        assert len(records) > 0
        assert records[0].is_miscalibrated == True
        assert records[0].calibration_error > 0

    def test_underconfident_judge_detected(self, tracker, mock_artifact_store):
        """Test: underconfident judge flagged (expected < actual)."""
        mock_artifact_store.query.return_value = [
            {'decision_id': f'd_{i}', 'confidence': 0.60, 'ground_truth_correct': i < 90}
            for i in range(100)
        ]

        records = tracker.measure_calibration('judge_a', 'weekly')

        assert len(records) > 0
        assert records[0].is_miscalibrated == True
        assert records[0].calibration_error < 0

    def test_disagreement_report_detects_trend(self, tracker, mock_artifact_store):
        """Test: disagreement report detects rising/falling trend."""
        early_decisions = [
            {'decision_id': f'd_{i}', 'confidence': 0.9, 'ground_truth_correct': True}
            for i in range(10)
        ]
        recent_decisions = [
            {'decision_id': f'd_{i+10}', 'confidence': 0.9, 'ground_truth_correct': False}
            for i in range(10)
        ]
        all_decisions = early_decisions + recent_decisions

        mock_artifact_store.query.return_value = all_decisions

        report = tracker.get_judge_disagreement_report('judge_a', 30)

        assert report['trend'] == 'rising'
        assert report['disagreement_rate'] == 0.5

    def test_trust_score_computation(self, tracker, mock_artifact_store):
        """Test: trust score combines disagreement + calibration."""
        decisions = [{'decision_id': f'd_{i}', 'confidence': 0.9, 'ground_truth_correct': i < 95} for i in range(100)]

        def query_side_effect(query_dict, limit=None):
            if query_dict.get('artifact_type') == 'control_decision':
                return decisions
            elif query_dict.get('artifact_type') == 'judge_calibration_record':
                return [{'calibration_id': 'cal_1', 'judge_id': 'judge_a', 'calibration_error': 0.03}]
            return []

        mock_artifact_store.query.side_effect = query_side_effect

        trust_score = tracker.compute_trust_score('judge_a', 30)

        assert 0.85 < trust_score < 1.0

    def test_calibration_immutably_stored(self, tracker, mock_artifact_store):
        """Test: calibration records stored with immutable flag."""
        mock_artifact_store.query.return_value = [
            {'decision_id': 'd_1', 'confidence': 0.9, 'ground_truth_correct': True}
        ]

        records = tracker.measure_calibration('judge_a', 'weekly')

        mock_artifact_store.put.assert_called()
        call_args_list = mock_artifact_store.put.call_args_list
        for call in call_args_list:
            args, kwargs = call
            if kwargs.get('namespace') == 'governance/calibration':
                assert kwargs.get('immutable') == True

    def test_fails_closed_on_no_decisions(self, tracker, mock_artifact_store):
        """Test: returns empty list if no decisions found (fail-closed)."""
        mock_artifact_store.query.return_value = []

        records = tracker.measure_calibration('judge_a', 'weekly')

        assert records == []

    def test_disagreement_fails_closed_on_error(self, tracker, mock_artifact_store):
        """Test: disagreement report emits error_artifact on failure."""
        mock_artifact_store.query.side_effect = RuntimeError("DB error")

        with patch.object(tracker, '_emit_error_artifact') as mock_emit:
            with pytest.raises(RuntimeError):
                tracker.get_judge_disagreement_report('judge_a', 30)
            mock_emit.assert_called()

    def test_confidence_bucket_filtering(self, tracker):
        """Test: confidence bucket filtering works."""
        decisions = [
            {'confidence': 0.55},
            {'confidence': 0.75},
            {'confidence': 0.92},
            {'confidence': 0.98},
        ]

        filtered = tracker._filter_by_confidence_bucket(decisions, '0.9-0.95')

        assert len(filtered) == 1
        assert filtered[0]['confidence'] == 0.92

    def test_calibration_multiple_buckets(self, tracker, mock_artifact_store):
        """Test: calibration tracks multiple confidence buckets."""
        decisions = [
            {'confidence': 0.55, 'ground_truth_correct': True},
            {'confidence': 0.65, 'ground_truth_correct': True},
            {'confidence': 0.75, 'ground_truth_correct': True},
            {'confidence': 0.92, 'ground_truth_correct': False},
        ]

        mock_artifact_store.query.return_value = decisions

        records = tracker.measure_calibration('judge_a', 'weekly')

        assert len(records) > 1

    def test_recommendation_critical_high_disagreement(self, tracker):
        """Test: recommendation is CRITICAL for disagreement > 10%."""
        rec = tracker._generate_recommendation(0.15, 'stable')
        assert 'CRITICAL' in rec
        assert '10%' in rec

    def test_recommendation_warning_rising_trend(self, tracker):
        """Test: recommendation is WARNING for rising disagreement."""
        rec = tracker._generate_recommendation(0.07, 'rising')
        assert 'WARNING' in rec
        assert 'rising' in rec.lower()

    def test_get_confidence_bucket_edge_cases(self, tracker):
        """Test: confidence bucket assignment for edge cases."""
        assert tracker._get_confidence_bucket(0.55) == '0.5-0.6'
        assert tracker._get_confidence_bucket(0.60) == '0.6-0.7'
        assert tracker._get_confidence_bucket(0.99) == '0.95-1.0'
        assert tracker._get_confidence_bucket(1.01) == '0.95-1.0'

    def test_check_decision_correctness_with_eval(self, tracker, mock_artifact_store):
        """Test: decision correctness from eval result."""
        decision = {'decision_id': 'd_1'}
        mock_artifact_store.query.return_value = [{'status': 'pass'}]

        is_correct = tracker._check_decision_correctness(decision)

        assert is_correct == True

    def test_check_decision_correctness_with_ground_truth(self, tracker, mock_artifact_store):
        """Test: decision correctness from ground truth."""
        decision = {'decision_id': 'd_1', 'ground_truth_correct': False}
        mock_artifact_store.query.return_value = []

        is_correct = tracker._check_decision_correctness(decision)

        assert is_correct == False

    def test_check_decision_correctness_defaults_true(self, tracker, mock_artifact_store):
        """Test: decision correctness defaults to True when unknown."""
        decision = {'decision_id': 'd_1'}
        mock_artifact_store.query.return_value = []

        is_correct = tracker._check_decision_correctness(decision)

        assert is_correct == True
