"""Fire custom alerts based on metrics."""

from datetime import datetime
from typing import List, Dict, Any, Optional


class AlertEngine:
    """Evaluate custom alerts against real metrics."""

    def __init__(self, artifact_store: Optional[Any] = None):
        self.store = artifact_store or {}
        self.alerts: List[Dict[str, Any]] = []
        self.false_positive_count = 0
        self.true_positive_count = 0
        self.fired_alerts_history: List[Dict[str, Any]] = []

    def add_alert(self, alert: Dict[str, Any]) -> None:
        """Add custom alert definition."""
        if not alert.get('alert_id'):
            raise ValueError("Alert must have alert_id")
        if not alert.get('condition'):
            raise ValueError("Alert must have condition")
        self.alerts.append(alert)

    def evaluate_all_alerts(self) -> List[Dict[str, Any]]:
        """Check all alerts against current metrics."""
        fired_alerts = []

        for alert in self.alerts:
            if not alert.get('active', True):
                continue

            metric_value = self._get_metric_value(alert['condition'])

            if metric_value > alert.get('threshold', 0):
                fired = {
                    'alert_id': alert['alert_id'],
                    'name': alert['name'],
                    'metric_value': metric_value,
                    'threshold': alert.get('threshold', 0),
                    'channel': alert.get('channel', 'slack'),
                    'severity': alert.get('severity', 'warning'),
                    'fired_at': datetime.utcnow().isoformat() + 'Z'
                }
                fired_alerts.append(fired)
                self.fired_alerts_history.append(fired)

        return fired_alerts

    def _get_metric_value(self, condition: str) -> float:
        """Get current value for metric."""
        snapshot = self.store.get('snapshot', {})
        metrics = snapshot.get('metrics', {})

        if condition == 'decision_divergence':
            return metrics.get('decision_divergence', {}).get('current', 0)
        elif condition == 'exception_rate':
            return metrics.get('exception_rate', {}).get('current', 0)
        elif condition == 'error_rate':
            return metrics.get('error_rate', {}).get('current', 0)
        elif condition == 'policy_regression':
            return metrics.get('policy_regression', {}).get('current', 0)

        return 0.0

    def record_false_positive(self) -> None:
        """Mark an alert as a false positive."""
        self.false_positive_count += 1

    def record_true_positive(self) -> None:
        """Mark an alert as a true positive."""
        self.true_positive_count += 1

    def get_false_positive_rate(self) -> float:
        """Calculate false positive rate for tuning."""
        total = self.false_positive_count + self.true_positive_count
        if total == 0:
            return 0.0
        return self.false_positive_count / total

    def get_alert_stats(self) -> Dict[str, Any]:
        """Get statistics on alert performance."""
        return {
            'total_alerts_configured': len(self.alerts),
            'active_alerts': sum(1 for a in self.alerts if a.get('active', True)),
            'false_positives': self.false_positive_count,
            'true_positives': self.true_positive_count,
            'false_positive_rate': self.get_false_positive_rate(),
            'total_fired': len(self.fired_alerts_history)
        }

    def disable_alert(self, alert_id: str) -> None:
        """Disable a specific alert."""
        for alert in self.alerts:
            if alert.get('alert_id') == alert_id:
                alert['active'] = False
                break

    def update_alert_threshold(self, alert_id: str, new_threshold: float) -> None:
        """Update threshold for an alert."""
        for alert in self.alerts:
            if alert.get('alert_id') == alert_id:
                alert['threshold'] = new_threshold
                break

    def get_recent_alerts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most recent fired alerts."""
        return self.fired_alerts_history[-limit:]
