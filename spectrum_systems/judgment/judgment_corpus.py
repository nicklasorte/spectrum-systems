"""JudgmentCorpus: Reusable atomic judgments + precedent query."""

import uuid
from datetime import datetime
from typing import Dict, Any, List
import subprocess


class JudgmentCorpus:
    """Manage reusable judgments and precedent queries."""

    def __init__(self, artifact_store):
        self.artifact_store = artifact_store
        self.code_version = self._get_code_version()

    def record_judgment(self, decision_context: str, decision: str, rationale: str, confidence: float) -> Dict[str, Any]:
        """Record an atomic judgment for reuse."""
        try:
            judgment = {
                'artifact_type': 'judgment_record',
                'judgment_id': str(uuid.uuid4()),
                'decision_context': decision_context,
                'decision': decision,
                'rationale': rationale,
                'confidence': confidence,
                'outcome_verified': False,
                'status': 'candidate',
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }

            self.artifact_store.put(judgment, namespace='governance/judgment_corpus', immutable=True)
            return judgment

        except Exception as e:
            self._emit_error_artifact(f"Judgment recording failed: {str(e)}")
            raise RuntimeError(f"Failed to record judgment: {str(e)}")

    def query_precedents(self, decision_context: str, similarity_threshold: float = 0.8) -> List[Dict[str, Any]]:
        """Query similar precedent judgments."""
        try:
            precedents = self.artifact_store.query({
                'artifact_type': 'judgment_record',
                'status': 'precedent'
            }, limit=1000)

            matching = [p for p in precedents if decision_context.lower() in p.get('decision_context', '').lower()]

            return matching

        except Exception as e:
            self._emit_error_artifact(f"Precedent query failed: {str(e)}")
            raise RuntimeError(f"Failed to query precedents: {str(e)}")

    def supersede_judgment(self, judgment_id: str, new_judgment_id: str) -> Dict[str, Any]:
        """Mark judgment as superseded by newer one."""
        try:
            supersession = {
                'artifact_type': 'judgment_supersession_log',
                'supersession_id': str(uuid.uuid4()),
                'superseded_judgment_id': judgment_id,
                'new_judgment_id': new_judgment_id,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }

            self.artifact_store.put(supersession, namespace='governance/judgment_corpus')
            return supersession

        except Exception as e:
            self._emit_error_artifact(f"Judgment supersession failed: {str(e)}")
            raise RuntimeError(f"Failed to supersede judgment: {str(e)}")

    def _get_code_version(self) -> str:
        try:
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except Exception:
            return 'unknown'

    def _emit_error_artifact(self, error_msg: str) -> None:
        error_artifact = {'artifact_type': 'error_artifact', 'source': 'JudgmentCorpus', 'error_message': error_msg, 'timestamp': datetime.utcnow().isoformat() + 'Z'}
        try:
            self.artifact_store.put(error_artifact, namespace='governance/errors')
        except Exception:
            pass
