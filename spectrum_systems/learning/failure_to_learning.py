"""FailureToLearningPipeline: Every failure auto-triggers learning."""

import uuid
from datetime import datetime
from typing import Dict, Any
import subprocess


class FailureToLearningPipeline:
    """Convert failures into learning artifacts."""

    def __init__(self, artifact_store):
        self.artifact_store = artifact_store
        self.code_version = self._get_code_version()

    def process_incident_to_learning(self, incident: Dict[str, Any]) -> Dict[str, Any]:
        """Convert incident to learning artifact."""
        try:
            incident_id = incident.get('incident_id', 'unknown')
            failure_type = incident.get('incident_type', 'unknown')
            root_cause = incident.get('root_cause', 'unknown')

            if failure_type == 'eval_miss':
                learning_action = 'eval_expansion'
            elif failure_type == 'decision_error':
                learning_action = 'policy_update'
            elif failure_type == 'trace_gap':
                learning_action = 'trace_hardening'
            elif failure_type == 'calibration_failure':
                learning_action = 'calibration_review'
            else:
                learning_action = 'eval_expansion'

            learning_record = {
                'artifact_type': 'failure_learning_record',
                'learning_id': str(uuid.uuid4()),
                'incident_id': incident_id,
                'failure_type': failure_type,
                'root_cause': root_cause,
                'learning_action': learning_action,
                'status': 'proposed',
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }

            self.artifact_store.put(learning_record, namespace='governance/learning', immutable=True)

            return learning_record

        except Exception as e:
            self._emit_error_artifact(f"Failure-to-learning conversion failed: {str(e)}")
            raise RuntimeError(f"Failed to convert failure to learning: {str(e)}")

    def verify_all_failures_learned(self) -> Dict[str, Any]:
        """Verify all incidents have corresponding learning artifacts."""
        try:
            incidents = self.artifact_store.query({'artifact_type': 'postmortem_artifact'}, limit=10000)
            learning = self.artifact_store.query({'artifact_type': 'failure_learning_record'}, limit=10000)

            learning_ids = {l.get('incident_id'): l for l in learning}
            unlearned = [i.get('incident_id') for i in incidents if i.get('incident_id') not in learning_ids]

            report = {
                'artifact_type': 'failure_learning_verification',
                'verification_id': str(uuid.uuid4()),
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'total_incidents': len(incidents),
                'learned_incidents': len(incidents) - len(unlearned),
                'unlearned_incidents': unlearned,
                'all_learned': len(unlearned) == 0
            }

            self.artifact_store.put(report, namespace='governance/reports')

            if not report['all_learned']:
                alert = {
                    'artifact_type': 'unlearned_failure_alert',
                    'alert_id': str(uuid.uuid4()),
                    'unlearned_count': len(unlearned),
                    'incident_ids': unlearned,
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'severity': 'high'
                }
                self.artifact_store.put(alert, namespace='governance/alerts')

            return report

        except Exception as e:
            self._emit_error_artifact(f"Learning verification failed: {str(e)}")
            raise RuntimeError(f"Failed to verify learning: {str(e)}")

    def _get_code_version(self) -> str:
        try:
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except Exception:
            return 'unknown'

    def _emit_error_artifact(self, error_msg: str) -> None:
        error_artifact = {'artifact_type': 'error_artifact', 'source': 'FailureToLearningPipeline', 'error_message': error_msg, 'timestamp': datetime.utcnow().isoformat() + 'Z'}
        try:
            self.artifact_store.put(error_artifact, namespace='governance/errors')
        except Exception:
            pass
