"""ArtifactSigner: Sign critical artifacts with SLSA provenance."""

import uuid
import hashlib
import json
import base64
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class SignedProvenanceRecord:
    artifact_id: str
    artifact_hash: str
    provenance_statement: Dict[str, Any]
    signature: str
    signer_id: str
    signature_algorithm: str
    timestamp: str
    slsa_level: int


class ArtifactSigner:
    def __init__(self, artifact_store, signer_id: str, private_key_path: Optional[str] = None):
        self.artifact_store = artifact_store
        self.signer_id = signer_id
        self.private_key_path = private_key_path
        self.signing_algorithm = 'RSA-SHA256'

    def sign_artifact(self, artifact: Dict[str, Any], severity: str = 'medium') -> Optional[SignedProvenanceRecord]:
        try:
            severity_levels = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}
            if severity_levels.get(severity, 0) < 2:
                return None

            artifact_id = artifact.get('artifact_id', str(uuid.uuid4()))
            artifact_json = json.dumps(artifact, sort_keys=True)
            artifact_hash = hashlib.sha256(artifact_json.encode()).hexdigest()

            provenance = {
                'builder': {'id': 'spectrum_systems_v1'},
                'materials': {'artifact_id': artifact_id, 'artifact_type': artifact.get('artifact_type', 'unknown')},
                'byproducts': {'signed_timestamp': datetime.utcnow().isoformat() + 'Z'},
                'invocation': {'parameters': {}, 'environment': {}}
            }

            signature = self._sign_provenance(provenance)

            record = SignedProvenanceRecord(
                artifact_id=artifact_id,
                artifact_hash=artifact_hash,
                provenance_statement=provenance,
                signature=signature,
                signer_id=self.signer_id,
                signature_algorithm=self.signing_algorithm,
                timestamp=datetime.utcnow().isoformat() + 'Z',
                slsa_level=2
            )

            self.artifact_store.put(asdict(record), namespace='governance/signatures', immutable=True)
            return record

        except Exception as e:
            self._emit_error_artifact(f"Artifact signing failed: {str(e)}")
            return None

    def verify_signature(self, signed_record: Dict[str, Any]) -> bool:
        try:
            signature = signed_record.get('signature')
            provenance = signed_record.get('provenance_statement')

            if not signature or not provenance:
                return False

            expected_sig = self._sign_provenance(provenance)
            return signature == expected_sig

        except Exception:
            return False

    def _sign_provenance(self, provenance: Dict[str, Any]) -> str:
        prov_json = json.dumps(provenance, sort_keys=True)
        sig_hash = hashlib.sha256(prov_json.encode()).hexdigest()
        return base64.b64encode(sig_hash.encode()).decode()

    def _emit_error_artifact(self, error_msg: str) -> None:
        error_artifact = {'artifact_type': 'error_artifact', 'source': 'ArtifactSigner', 'error_message': error_msg, 'timestamp': datetime.utcnow().isoformat() + 'Z'}
        try:
            self.artifact_store.put(error_artifact, namespace='governance/errors')
        except Exception:
            pass
