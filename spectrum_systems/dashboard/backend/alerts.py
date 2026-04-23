"""Alert generation and runbook linkage."""

from typing import Dict, Any, List
from datetime import datetime


class AlertEngine:
    """Generate alerts from health metrics."""

    def __init__(self):
        self.thresholds = {
            'health_score_critical': 50,
            'health_score_warning': 70,
            'incidents_week_warning': 3,
            'contract_violations_critical': 1,
        }

        self.runbook_base_url = 'https://spectrum-systems.example.com/runbooks'

    def generate_alerts(self, health_scores: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate alerts from health data."""
        alerts = []

        for system_id, metrics in health_scores.items():
            # Critical health score
            if metrics['health_score'] < self.thresholds['health_score_critical']:
                alerts.append({
                    'severity': 'critical',
                    'system_id': system_id,
                    'title': f"{system_id} health critical: {metrics['health_score']}%",
                    'description': f"{metrics['system_name']} has dropped below critical threshold",
                    'metric': 'health_score',
                    'value': metrics['health_score'],
                    'threshold': self.thresholds['health_score_critical'],
                    'runbook': self._get_runbook(system_id, 'health_critical'),
                    'alert_id': f"{system_id}-health-critical",
                    'generated_at': datetime.utcnow().isoformat(),
                })

            # Warning health score
            elif metrics['health_score'] < self.thresholds['health_score_warning']:
                alerts.append({
                    'severity': 'warning',
                    'system_id': system_id,
                    'title': f"{system_id} health warning: {metrics['health_score']}%",
                    'description': f"{metrics['system_name']} health is degrading",
                    'metric': 'health_score',
                    'value': metrics['health_score'],
                    'threshold': self.thresholds['health_score_warning'],
                    'runbook': self._get_runbook(system_id, 'health_warning'),
                    'alert_id': f"{system_id}-health-warning",
                    'generated_at': datetime.utcnow().isoformat(),
                })

            # High incident count
            if metrics['incident_count'] >= self.thresholds['incidents_week_warning']:
                alerts.append({
                    'severity': 'warning',
                    'system_id': system_id,
                    'title': f"{system_id} incident surge: {metrics['incident_count']} this week",
                    'description': f"{metrics['system_name']} has experienced elevated incidents",
                    'metric': 'incident_count',
                    'value': metrics['incident_count'],
                    'threshold': self.thresholds['incidents_week_warning'],
                    'runbook': self._get_runbook(system_id, 'incident_surge'),
                    'alert_id': f"{system_id}-incident-surge",
                    'generated_at': datetime.utcnow().isoformat(),
                })

            # Contract violations
            violations = metrics.get('contract_violations', [])
            if len(violations) >= self.thresholds['contract_violations_critical']:
                alerts.append({
                    'severity': 'critical',
                    'system_id': system_id,
                    'title': f"{system_id} contract violation: {violations[0].get('rule', 'unknown')}",
                    'description': f"{metrics['system_name']} violating contract rule",
                    'metric': 'contract_violations',
                    'value': len(violations),
                    'threshold': self.thresholds['contract_violations_critical'],
                    'runbook': self._get_runbook(system_id, 'contract_violation'),
                    'violations': violations,
                    'alert_id': f"{system_id}-contract-violation",
                    'generated_at': datetime.utcnow().isoformat(),
                })

        return alerts

    def _get_runbook(self, system_id: str, alert_type: str) -> str:
        """Get runbook URL for this alert."""
        return f'{self.runbook_base_url}/{system_id}/{alert_type}.md'

    def filter_alerts_by_severity(
        self,
        alerts: List[Dict[str, Any]],
        severity: str,
    ) -> List[Dict[str, Any]]:
        """Filter alerts by severity level."""
        return [a for a in alerts if a['severity'] == severity]

    def dedup_alerts(
        self,
        alerts: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Remove duplicate alerts, keeping most recent."""
        seen = {}
        for alert in reversed(alerts):
            alert_id = alert.get('alert_id')
            if alert_id and alert_id not in seen:
                seen[alert_id] = alert

        return list(seen.values())
