"""CanonicalTruthManager: Single source of truth for system state."""

import uuid
import hashlib
import json
from datetime import datetime
from typing import Dict, Any
from dataclasses import dataclass, asdict
import subprocess


@dataclass
class CanonicalTruthRecord:
    canonical_id: str
    canonical_version: str
    canonical_data: Dict[str, Any]
    hash: str
    created_timestamp: str
    last_verified_timestamp: str
    drift_detected: bool


class CanonicalTruthManager:
    def __init__(self, artifact_store):
        self.artifact_store = artifact_store
        self.code_version = self._get_code_version()

    def create_canonical_truth(self, canonical_id: str, canonical_data: Dict[str, Any], version: str = '1.0.0') -> CanonicalTruthRecord:
        try:
            if not canonical_data:
                raise ValueError("canonical_data cannot be empty")

            data_json = json.dumps(canonical_data, sort_keys=True)
            hash_value = hashlib.sha256(data_json.encode()).hexdigest()

            record = CanonicalTruthRecord(
                canonical_id=canonical_id,
                canonical_version=version,
                canonical_data=canonical_data,
                hash=hash_value,
                created_timestamp=datetime.utcnow().isoformat() + 'Z',
                last_verified_timestamp=datetime.utcnow().isoformat() + 'Z',
                drift_detected=False
            )

            self.artifact_store.put(asdict(record), namespace='governance/canonical_truth', immutable=True)
            return record

        except Exception as e:
            self._emit_error_artifact(f"Canonical truth creation failed: {str(e)}")
            raise RuntimeError(f"Failed to create canonical truth: {str(e)}")

    def verify_against_canonical(self, canonical_id: str, current_state: Dict[str, Any]) -> Dict[str, Any]:
        try:
            canonical = self.artifact_store.query({'artifact_type': 'canonical_truth_manifest', 'canonical_id': canonical_id}, limit=1)

            if not canonical:
                return {'drift_detected': True, 'reason': 'Canonical not found', 'status': 'critical'}

            canonical = canonical[0]
            current_json = json.dumps(current_state, sort_keys=True)
            current_hash = hashlib.sha256(current_json.encode()).hexdigest()

            canonical_hash = canonical.get('hash')
            drift_detected = current_hash != canonical_hash

            report = {
                'artifact_type': 'drift_from_canonical_signal',
                'report_id': str(uuid.uuid4()),
                'canonical_id': canonical_id,
                'canonical_hash': canonical_hash,
                'current_hash': current_hash,
                'drift_detected': drift_detected,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }

            self.artifact_store.put(report, namespace='governance/reports')
            return report

        except Exception as e:
            self._emit_error_artifact(f"Canonical verification failed: {str(e)}")
            raise RuntimeError(f"Failed to verify canonical: {str(e)}")

    def _get_code_version(self) -> str:
        try:
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except Exception:
            return 'unknown'

    def _emit_error_artifact(self, error_msg: str) -> None:
        error_artifact = {'artifact_type': 'error_artifact', 'source': 'CanonicalTruthManager', 'error_message': error_msg, 'timestamp': datetime.utcnow().isoformat() + 'Z'}
        try:
            self.artifact_store.put(error_artifact, namespace='governance/errors')
        except Exception:
            pass
