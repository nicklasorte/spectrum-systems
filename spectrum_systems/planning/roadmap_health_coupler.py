"""RoadmapHealthCoupler: Drive roadmap from system health."""

import uuid
from datetime import datetime
from typing import Dict, Any
import subprocess


class RoadmapHealthCoupler:
    def __init__(self, artifact_store):
        self.artifact_store = artifact_store
        self.code_version = self._get_code_version()

    def generate_priority_report(self) -> Dict[str, Any]:
        try:
            health = self.artifact_store.query({'artifact_type': 'entropy_posture_snapshot'}, limit=1)

            if not health:
                health_status = 'unknown'
                health_metrics = {}
            else:
                health_data = health[0]
                decision_divergence = health_data.get('metrics', {}).get('decision_divergence', {}).get('current', 0)
                exception_rate = health_data.get('metrics', {}).get('exception_rate', {}).get('current', 0)

                health_metrics = {'decision_divergence': decision_divergence, 'exception_rate': exception_rate}

                if decision_divergence > 0.15 or exception_rate > 0.05:
                    health_status = 'critical'
                elif decision_divergence > 0.10 or exception_rate > 0.02:
                    health_status = 'degraded'
                else:
                    health_status = 'healthy'

            if health_status == 'critical':
                prioritized = ['fix_drift', 'reduce_exceptions', 'emergency_review']
                paused = ['new_features', 'optimization', 'refactoring']
            elif health_status == 'degraded':
                prioritized = ['stabilize_drift', 'monitor_exceptions']
                paused = ['optimization']
            else:
                prioritized = []
                paused = []

            report = {
                'artifact_type': 'roadmap_priority_report',
                'report_id': str(uuid.uuid4()),
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'current_health': health_status,
                'health_metrics': health_metrics,
                'prioritized_items': prioritized,
                'paused_items': paused,
                'recommendation': self._generate_recommendation(health_status)
            }

            self.artifact_store.put(report, namespace='governance/reports')
            return report

        except Exception as e:
            self._emit_error_artifact(f"Priority report generation failed: {str(e)}")
            raise RuntimeError(f"Failed to generate priority report: {str(e)}")

    def _generate_recommendation(self, health_status: str) -> str:
        if health_status == 'critical':
            return 'HALT NON-CRITICAL WORK. Focus on stabilization.'
        elif health_status == 'degraded':
            return 'Pause optimization. Maintain focus on stability.'
        else:
            return 'Proceed with roadmap as planned.'

    def _get_code_version(self) -> str:
        try:
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except Exception:
            return 'unknown'

    def _emit_error_artifact(self, error_msg: str) -> None:
        error_artifact = {'artifact_type': 'error_artifact', 'source': 'RoadmapHealthCoupler', 'error_message': error_msg, 'timestamp': datetime.utcnow().isoformat() + 'Z'}
        try:
            self.artifact_store.put(error_artifact, namespace='governance/errors')
        except Exception:
            pass
