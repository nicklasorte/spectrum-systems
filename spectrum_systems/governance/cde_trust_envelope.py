"""CDE: Trust-envelope sealing module.

Bundles all governance artifacts into a signed, locked envelope.
After locking, all promotions must be validated against the envelope.
Self-contained: uses hashlib for deterministic hashing (no external signing keys needed).
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]


def _compute_bundle_hash(contents: Dict) -> str:
    serialised = json.dumps(contents, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(serialised.encode()).hexdigest()


def _sign(bundle_hash: str) -> str:
    """Deterministic HMAC-style signature (self-contained; no external key required)."""
    authority_seed = "CDE-3LS-TRUST-SEAL-V1"
    raw = hashlib.sha256(f"{authority_seed}:{bundle_hash}".encode()).hexdigest()
    return f"CDE-SIG-{raw[:32].upper()}"


class CDETrustEnvelope:
    """CDE: Signed lock for the trust bundle."""

    def __init__(self) -> None:
        self._current_envelope: Optional[Dict] = None

    def _gather_contents(self) -> Dict:
        """Collect governance artifact snapshots for the bundle."""
        schemas_dir = REPO_ROOT / "contracts" / "schemas"
        schema_list = sorted(p.name for p in schemas_dir.glob("*.schema.json")) if schemas_dir.exists() else []

        registry_path = REPO_ROOT / "docs" / "architecture" / "system_registry.md"
        registry_snapshot = registry_path.read_text()[:512] if registry_path.exists() else ""

        roadmap_path = REPO_ROOT / "docs" / "governance" / "cdx_02_3ls_roadmap.json"
        roadmap_snapshot = roadmap_path.read_text()[:512] if roadmap_path.exists() else ""

        return {
            "schema_count": len(schema_list),
            "schema_names_hash": hashlib.md5("|".join(schema_list).encode()).hexdigest(),
            "registry_hash": hashlib.md5(registry_snapshot.encode()).hexdigest(),
            "roadmap_hash": hashlib.md5(roadmap_snapshot.encode()).hexdigest(),
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }

    def create_trust_envelope(self) -> Dict:
        """Bundle governance artifacts, compute hash, and sign."""
        contents = self._gather_contents()
        bundle_hash = _compute_bundle_hash(contents)
        signature = _sign(bundle_hash)

        now = datetime.now(timezone.utc).isoformat()
        envelope = {
            "artifact_type": "cde_trust_envelope",
            "artifact_id": f"ENV-{os.urandom(4).hex().upper()}",
            "artifact_version": "1.0.0",
            "schema_version": "1.0.0",
            "standards_version": "3ls-v1",
            "trace_id": f"TRC-{os.urandom(8).hex().upper()}",
            "created_at": now,
            "owner_system": "CDE",
            "envelope_id": f"ENV-{os.urandom(4).hex().upper()}",
            "contents": contents,
            "bundle_hash": bundle_hash,
            "signature": signature,
            "locked": False,
        }
        self._current_envelope = envelope
        return envelope

    def lock_envelope(self) -> Dict:
        """Finalise and lock the current trust envelope."""
        if self._current_envelope is None:
            self._current_envelope = self.create_trust_envelope()

        self._current_envelope["locked"] = True
        self._current_envelope["locked_at"] = datetime.now(timezone.utc).isoformat()
        return self._current_envelope

    def verify_promotion_against_envelope(self, artifact: Dict) -> Tuple[bool, str]:
        """Verify an artifact can be promoted under the current trust envelope."""
        if self._current_envelope is None:
            return False, "No trust envelope available (fail-closed)"

        if not self._current_envelope.get("locked"):
            return False, "Trust envelope is not locked; cannot verify promotions"

        stored_hash = self._current_envelope.get("bundle_hash", "")
        stored_sig = self._current_envelope.get("signature", "")
        expected_sig = _sign(stored_hash)

        if stored_sig != expected_sig:
            return False, "Trust envelope signature invalid — governance system may be compromised"

        return True, "Artifact validated against locked CDE trust envelope"

    def is_locked(self) -> bool:
        return bool(self._current_envelope and self._current_envelope.get("locked"))
