"""EntropyDashboard: Weekly entropy aggregation + auto-hardening logic."""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List
import subprocess


class EntropyDashboard:
    """Aggregate weekly entropy metrics and drive control decisions."""

    def __init__(self, artifact_store):
        self.artifact_store = artifact_store
        self.code_version = self._get_code_version()

    def generate_weekly_snapshot(self) -> Dict[str, Any]:
        """Generate weekly entropy posture snapshot."""
        try:
            week_ago = datetime.utcnow() - timedelta(days=7)

            drift_signals = self.artifact_store.query({'artifact_type': 'drift_signal_record', 'recency_days': 7}, limit=1000)
            exception_artifacts = self.artifact_store.query({'artifact_type': 'exception_artifact', 'recency_days': 7}, limit=1000)
            trace_audits = self.artifact_store.query({'artifact_type': 'trace_coverage_audit', 'recency_days': 7}, limit=100)
            calibration_records = self.artifact_store.query({'artifact_type': 'judge_calibration_record', 'recency_days': 7}, limit=1000)
            hotspot_reports = self.artifact_store.query({'artifact_type': 'override_hotspot_report', 'recency_days': 7}, limit=10)

            metrics = {
                'decision_divergence': {
                    'current': self._avg_metric([d.get('decision_divergence', 0) for d in drift_signals]),
                    'trend': self._detect_trend([d.get('decision_divergence', 0) for d in drift_signals]),
                    'threshold': 0.10
                },
                'exception_rate': {
                    'current': len(exception_artifacts) / 7 if exception_artifacts else 0,
                    'trend': 'stable',
                    'threshold': 0.02
                },
                'trace_coverage': {
                    'current': trace_audits[0].get('coverage_percent', 0) if trace_audits else 0,
                    'slo': 0.999,
                    'met': trace_audits[0].get('slo_met', False) if trace_audits else False
                },
                'calibration_drift': {
                    'current': self._avg_metric([abs(c.get('calibration_error', 0)) for c in calibration_records]),
                    'threshold': 0.05
                },
                'override_hotspots': {
                    'count': len(hotspot_reports[0].get('high_risk_gates', [])) if hotspot_reports else 0,
                    'action': 'escalate' if hotspot_reports and len(hotspot_reports[0].get('high_risk_gates', [])) > 0 else 'monitor'
                },
                'failure_to_eval_rate': {
                    'current': self._compute_failure_eval_rate(),
                    'threshold': 0.01
                }
            }

            control_decisions = self._compute_control_decisions(metrics)

            snapshot = {
                'artifact_type': 'entropy_posture_snapshot',
                'snapshot_id': str(uuid.uuid4()),
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'week_ending': (datetime.utcnow().date()).isoformat(),
                'metrics': metrics,
                'control_decisions': control_decisions,
                'recommendation': self._generate_recommendation(metrics, control_decisions)
            }

            self.artifact_store.put(snapshot, namespace='governance/snapshots')
            return snapshot

        except Exception as e:
            self._emit_error_artifact(f"Entropy snapshot generation failed: {str(e)}")
            raise RuntimeError(f"Failed to generate entropy snapshot: {str(e)}")

    def _avg_metric(self, values: List[float]) -> float:
        """Compute average metric."""
        return sum(values) / len(values) if values else 0

    def _detect_trend(self, values: List[float]) -> str:
        """Detect trend in metric over time."""
        if len(values) < 2:
            return 'stable'

        recent = values[-3:] if len(values) >= 3 else values
        early = values[:3] if len(values) >= 3 else values

        recent_avg = sum(recent) / len(recent)
        early_avg = sum(early) / len(early)

        if recent_avg > early_avg * 1.1:
            return 'rising'
        elif recent_avg < early_avg * 0.9:
            return 'falling'
        else:
            return 'stable'

    def _compute_failure_eval_rate(self) -> float:
        """Compute failures that weren't caught by evals."""
        try:
            incidents = self.artifact_store.query({'artifact_type': 'postmortem_artifact', 'recency_days': 7}, limit=100)
            evals = self.artifact_store.query({'artifact_type': 'eval_case', 'recency_days': 7}, limit=10000)

            if not incidents:
                return 0

            missed = sum(1 for i in incidents if i.get('incident_type') == 'eval_miss')
            return missed / len(incidents) if incidents else 0

        except Exception:
            return 0

    def _compute_control_decisions(self, metrics: Dict[str, Any]) -> List[str]:
        """Compute control decisions based on metrics."""
        decisions = []

        if metrics['decision_divergence']['current'] > 0.20:
            decisions.append('block')
        elif metrics['decision_divergence']['current'] > 0.15:
            decisions.append('escalate')

        if metrics['exception_rate']['current'] > 0.05:
            decisions.append('escalate')

        if not metrics['trace_coverage']['met']:
            decisions.append('escalate')

        if metrics['override_hotspots']['count'] > 3:
            decisions.append('escalate')

        if len(decisions) == 0:
            decisions.append('proceed')

        return list(set(decisions))

    def _generate_recommendation(self, metrics: Dict[str, Any], decisions: List[str]) -> str:
        """Generate recommendation based on metrics and decisions."""
        if 'block' in decisions:
            return 'CRITICAL: System entropy critical. Block all promotions. Emergency review required.'
        elif 'escalate' in decisions:
            return 'WARNING: System entropy elevated. Escalate to governance council. Proceed with caution.'
        else:
            return 'System entropy nominal. Proceed with normal operations.'

    def _get_code_version(self) -> str:
        try:
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except Exception:
            return 'unknown'

    def _emit_error_artifact(self, error_msg: str) -> None:
        error_artifact = {'artifact_type': 'error_artifact', 'source': 'EntropyDashboard', 'error_message': error_msg, 'timestamp': datetime.utcnow().isoformat() + 'Z'}
        try:
            self.artifact_store.put(error_artifact, namespace='governance/errors')
        except Exception:
            pass
