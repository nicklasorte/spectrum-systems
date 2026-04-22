"""ContextTrustModel: Rate context trustworthiness."""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Any
import subprocess


class ContextTrustModel:
    """Score and admit context based on trustworthiness."""

    def __init__(self, artifact_store):
        self.artifact_store = artifact_store
        self.code_version = self._get_code_version()

    def score_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Score context trustworthiness."""
        try:
            context_id = context.get('context_id', str(uuid.uuid4()))
            source = context.get('source', 'unknown')
            created_at = context.get('created_at')

            freshness_score = self._compute_freshness(created_at)
            accuracy_score = self._compute_accuracy(context)
            completeness_score = self._compute_completeness(context)

            overall = (freshness_score * accuracy_score * completeness_score) ** (1/3)

            if overall >= 0.9:
                admission = 'admit'
            elif overall >= 0.7:
                admission = 'quarantine'
            else:
                admission = 'reject'

            record = {
                'artifact_type': 'context_trust_score',
                'context_id': context_id,
                'source': source,
                'freshness_score': freshness_score,
                'accuracy_score': accuracy_score,
                'completeness_score': completeness_score,
                'overall_trust_score': overall,
                'admission_decision': admission,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }

            self.artifact_store.put(record, namespace='governance/trust')
            return record

        except Exception as e:
            self._emit_error_artifact(f"Context trust scoring failed: {str(e)}")
            raise RuntimeError(f"Failed to score context: {str(e)}")

    def _compute_freshness(self, created_at: str) -> float:
        """Freshness score: newer = higher."""
        try:
            if not created_at:
                return 0.5

            created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            age_hours = (datetime.utcnow() - created).total_seconds() / 3600

            freshness = max(0, 1.0 - (age_hours / 24) * 0.1)
            return min(1.0, freshness)

        except Exception:
            return 0.5

    def _compute_accuracy(self, context: Dict[str, Any]) -> float:
        """Accuracy score: check against validation signals."""
        try:
            context_id = context.get('context_id')
            evals = self.artifact_store.query({'context_id': context_id, 'artifact_type': 'eval_result'}, limit=10)

            if not evals:
                return 0.75

            passed = sum(1 for e in evals if e.get('status') == 'pass')
            accuracy = passed / len(evals) if evals else 0.5
            return accuracy

        except Exception:
            return 0.75

    def _compute_completeness(self, context: Dict[str, Any]) -> float:
        """Completeness score: required fields present."""
        required_fields = ['source', 'created_at', 'data']
        present = sum(1 for field in required_fields if context.get(field))
        completeness = present / len(required_fields)
        return completeness

    def _get_code_version(self) -> str:
        try:
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except Exception:
            return 'unknown'

    def _emit_error_artifact(self, error_msg: str) -> None:
        error_artifact = {'artifact_type': 'error_artifact', 'source': 'ContextTrustModel', 'error_message': error_msg, 'timestamp': datetime.utcnow().isoformat() + 'Z'}
        try:
            self.artifact_store.put(error_artifact, namespace='governance/errors')
        except Exception:
            pass
