"""
JudgeCalibrationTracker: Measure judge confidence vs actual correctness longitudinally.
Detect overconfidence, underconfidence, systematic bias.
NIST warning: confidence without calibration is unusable.
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import subprocess


@dataclass
class CalibrationRecord:
    """Single calibration measurement."""
    calibration_id: str
    judge_id: str
    confidence_bucket: str
    total_decisions: int
    correct_decisions: int
    actual_accuracy: float
    expected_accuracy: float
    calibration_error: float
    is_miscalibrated: bool
    measurement_period: str
    timestamp: str
    source_code_version: str


class JudgeCalibrationTracker:
    """
    Track judge calibration over time.

    Principle: Confidence must match observed accuracy.
    Overconfidence is the deadliest failure mode (NIST).
    """

    def __init__(self, artifact_store, eval_runner=None):
        self.artifact_store = artifact_store
        self.eval_runner = eval_runner
        self.code_version = self._get_code_version()
        self.miscalibration_threshold = 0.05

    def measure_calibration(self, judge_id: str, measurement_period: str = 'weekly') -> List[CalibrationRecord]:
        """
        Measure judge calibration for all confidence buckets.

        Algorithm:
        1. Fetch decisions made by judge in period
        2. For each confidence bucket:
           a. Group decisions by stated confidence
           b. Measure actual accuracy (ground truth)
           c. Compare to stated confidence
           d. Calculate calibration_error
           e. Flag if miscalibrated
        3. Store records immutably
        4. Fail-closed: any error → emit error_artifact, block decision

        Returns: List of CalibrationRecord (one per bucket)
        """
        try:
            period_days = {'daily': 1, 'weekly': 7, 'monthly': 30}.get(measurement_period, 7)

            decisions = self.artifact_store.query({
                'artifact_type': 'control_decision',
                'judge_id': judge_id,
                'recency_days': period_days
            }, limit=10000)

            if not decisions:
                return []

            buckets = [
                ('0.5-0.6', 0.55),
                ('0.6-0.7', 0.65),
                ('0.7-0.8', 0.75),
                ('0.8-0.9', 0.85),
                ('0.9-0.95', 0.925),
                ('0.95-1.0', 0.975),
            ]

            records = []

            for bucket_name, expected_acc in buckets:
                bucket_decisions = self._filter_by_confidence_bucket(decisions, bucket_name)

                if not bucket_decisions:
                    continue

                correct_count = 0
                for decision in bucket_decisions:
                    is_correct = self._check_decision_correctness(decision)
                    if is_correct:
                        correct_count += 1

                actual_accuracy = correct_count / len(bucket_decisions)
                calibration_error = expected_acc - actual_accuracy
                is_miscalibrated = abs(calibration_error) > self.miscalibration_threshold

                record = CalibrationRecord(
                    calibration_id=str(uuid.uuid4()),
                    judge_id=judge_id,
                    confidence_bucket=bucket_name,
                    total_decisions=len(bucket_decisions),
                    correct_decisions=correct_count,
                    actual_accuracy=actual_accuracy,
                    expected_accuracy=expected_acc,
                    calibration_error=calibration_error,
                    is_miscalibrated=is_miscalibrated,
                    measurement_period=measurement_period,
                    timestamp=datetime.utcnow().isoformat() + 'Z',
                    source_code_version=self.code_version
                )

                self.artifact_store.put(
                    asdict(record),
                    namespace='governance/calibration',
                    immutable=True
                )

                records.append(record)

            return records

        except Exception as e:
            self._emit_error_artifact(f"Calibration measurement failed: {str(e)}")
            raise RuntimeError(f"JudgeCalibrationTracker.measure_calibration failed: {str(e)}")

    def get_judge_disagreement_report(self, judge_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Measure judge disagreement with ground truth over time.

        Metrics:
        - Disagreement rate (how often judge disagrees with ground truth)
        - Trend (rising, stable, falling)
        - Severity buckets (by confidence)

        Returns: judge_disagreement_report artifact
        """
        try:
            decisions = self.artifact_store.query({
                'artifact_type': 'control_decision',
                'judge_id': judge_id,
                'recency_days': days
            }, limit=10000)

            if not decisions:
                return {
                    'judge_id': judge_id,
                    'period_days': days,
                    'total_decisions': 0,
                    'disagreement_rate': 0,
                    'trend': 'unknown',
                    'severity_breakdown': {},
                    'recommendation': 'Insufficient data'
                }

            disagreement_count = 0
            disagreement_by_confidence = {}

            for decision in decisions:
                is_correct = self._check_decision_correctness(decision)
                if not is_correct:
                    disagreement_count += 1

                    conf = decision.get('confidence', 0.5)
                    bucket = self._get_confidence_bucket(conf)
                    if bucket not in disagreement_by_confidence:
                        disagreement_by_confidence[bucket] = []
                    disagreement_by_confidence[bucket].append(decision)

            disagreement_rate = disagreement_count / len(decisions) if decisions else 0

            recent = decisions[-10:] if len(decisions) >= 10 else decisions
            early = decisions[:10] if len(decisions) >= 10 else decisions

            recent_disagreement = sum(1 for d in recent if not self._check_decision_correctness(d))
            early_disagreement = sum(1 for d in early if not self._check_decision_correctness(d))

            recent_rate = recent_disagreement / len(recent) if recent else 0
            early_rate = early_disagreement / len(early) if early else 0

            if recent_rate > early_rate * 1.1:
                trend = 'rising'
            elif recent_rate < early_rate * 0.9:
                trend = 'falling'
            else:
                trend = 'stable'

            report = {
                'artifact_type': 'judge_disagreement_report',
                'report_id': str(uuid.uuid4()),
                'judge_id': judge_id,
                'period_days': days,
                'total_decisions': len(decisions),
                'disagreement_count': disagreement_count,
                'disagreement_rate': disagreement_rate,
                'trend': trend,
                'severity_breakdown': {
                    bucket: {
                        'count': len(decisions),
                        'rate': len(decisions) / len(decisions) if decisions else 0
                    }
                    for bucket, decisions in disagreement_by_confidence.items()
                },
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'recommendation': self._generate_recommendation(disagreement_rate, trend)
            }

            self.artifact_store.put(report, namespace='governance/reports')

            return report

        except Exception as e:
            self._emit_error_artifact(f"Disagreement report failed: {str(e)}")
            raise RuntimeError(f"Judge disagreement report failed: {str(e)}")

    def compute_trust_score(self, judge_id: str, days: int = 30) -> float:
        """
        Compute trust score for judge (0-1).

        Formula:
        trust_score = (1 - disagreement_rate) * (1 - calibration_error)

        Returns: float 0-1 (0 = don't trust, 1 = fully trust)
        """
        try:
            report = self.get_judge_disagreement_report(judge_id, days)
            disagreement_rate = report.get('disagreement_rate', 0)

            calibrations = self.artifact_store.query({
                'artifact_type': 'judge_calibration_record',
                'judge_id': judge_id,
                'recency_days': days
            }, limit=100)

            if not calibrations:
                return 1 - disagreement_rate

            avg_calibration_error = sum(abs(c.get('calibration_error', 0)) for c in calibrations) / len(calibrations)

            trust_score = (1 - disagreement_rate) * (1 - avg_calibration_error)

            return max(0, min(1, trust_score))

        except Exception:
            return 0

    def _filter_by_confidence_bucket(self, decisions: List[Dict], bucket: str) -> List[Dict]:
        """Filter decisions by confidence bucket."""
        low, high = map(float, bucket.split('-'))
        matching = []

        for decision in decisions:
            conf = decision.get('confidence', 0.5)
            if low <= conf < high:
                matching.append(decision)

        return matching

    def _get_confidence_bucket(self, confidence: float) -> str:
        """Get bucket name for a confidence value."""
        buckets = [
            ('0.5-0.6', 0.5, 0.6),
            ('0.6-0.7', 0.6, 0.7),
            ('0.7-0.8', 0.7, 0.8),
            ('0.8-0.9', 0.8, 0.9),
            ('0.9-0.95', 0.9, 0.95),
            ('0.95-1.0', 0.95, 1.0),
        ]

        for name, low, high in buckets:
            if low <= confidence < high:
                return name

        return '0.95-1.0'

    def _check_decision_correctness(self, decision: Dict) -> bool:
        """Check if decision was correct (via eval or golden data)."""
        try:
            eval_result = self.artifact_store.query({
                'artifact_type': 'eval_result',
                'decision_id': decision.get('decision_id')
            }, limit=1)

            if eval_result and eval_result[0].get('status') == 'pass':
                return True

            golden_truth = decision.get('ground_truth_correct')
            if golden_truth is not None:
                return golden_truth

            return True

        except Exception:
            return False

    def _generate_recommendation(self, disagreement_rate: float, trend: str) -> str:
        """Generate recommendation based on metrics."""
        if disagreement_rate > 0.1:
            return 'CRITICAL: Judge disagreement rate > 10%. Escalate for review.'
        elif disagreement_rate > 0.05 and trend == 'rising':
            return 'WARNING: Judge disagreement rising. Monitor closely.'
        elif disagreement_rate > 0.05:
            return 'WARNING: Judge disagreement rate > 5%. Consider retraining.'
        else:
            return 'Judge performing well. Continue monitoring.'

    def _get_code_version(self) -> str:
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except Exception:
            return 'unknown'

    def _emit_error_artifact(self, error_msg: str) -> None:
        error_artifact = {
            'artifact_type': 'error_artifact',
            'source': 'JudgeCalibrationTracker',
            'error_message': error_msg,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        try:
            self.artifact_store.put(error_artifact, namespace='governance/errors')
        except Exception:
            pass
