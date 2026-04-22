"""REL: Release semantics — canary, freeze, rollback record emission.

Promotion is blocked unless a canary_record exists for the artifact.
SLO breaches trigger freeze_record emission.
Rollback emits a rollback_record with the revert steps.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict, List, Tuple


class ReleaseSemanticsGate:
    """Enforces canary-before-promotion and manages freeze/rollback records."""

    def __init__(self) -> None:
        self._canary_records: Dict[str, Dict] = {}  # artifact_id → canary_record

    # ── canary ────────────────────────────────────────────────────────────

    def emit_canary_record(self, artifact_id: str, canary_scope: str) -> Dict:
        """Start a canary release and record it."""
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "artifact_type": "canary_record",
            "artifact_id": f"CAN-{os.urandom(4).hex().upper()}",
            "artifact_version": "1.0.0",
            "schema_version": "1.0.0",
            "standards_version": "3ls-v1",
            "trace_id": f"TRC-{os.urandom(8).hex().upper()}",
            "created_at": now,
            "owner_system": "REL",
            "source_artifact": artifact_id,
            "canary_scope": canary_scope,
            "started_at": now,
            "status": "running",
        }
        self._canary_records[artifact_id] = record
        return record

    def require_canary_before_promotion(self, artifact_id: str) -> Tuple[bool, str]:
        """Return (True, ok) if a canary_record exists; (False, reason) otherwise."""
        if artifact_id not in self._canary_records:
            return False, f"Artifact '{artifact_id}' has no canary_record; canary required before full promotion"
        canary = self._canary_records[artifact_id]
        if canary.get("status") == "failed":
            return False, f"Canary for '{artifact_id}' failed; promotion blocked"
        return True, f"Canary record {canary['artifact_id']} present; promotion allowed"

    # ── freeze ────────────────────────────────────────────────────────────

    def emit_freeze_record(self, artifact_id: str, reason: str) -> Dict:
        """Emit a freeze_record blocking promotion due to SLO breach or drift."""
        now = datetime.now(timezone.utc).isoformat()
        return {
            "artifact_type": "freeze_record",
            "artifact_id": f"FRZ-{os.urandom(4).hex().upper()}",
            "artifact_version": "1.0.0",
            "schema_version": "1.0.0",
            "standards_version": "3ls-v1",
            "trace_id": f"TRC-{os.urandom(8).hex().upper()}",
            "created_at": now,
            "owner_system": "REL",
            "freeze_id": f"FRZ-{os.urandom(4).hex().upper()}",
            "scope": artifact_id,
            "reason_codes": [reason],
        }

    # ── rollback ──────────────────────────────────────────────────────────

    def emit_rollback_record(self, artifact_id: str, revert_steps: List[str]) -> Dict:
        """Record a rollback of a promoted artifact."""
        now = datetime.now(timezone.utc).isoformat()
        return {
            "artifact_type": "rollback_record",
            "artifact_id": f"RBK-{os.urandom(4).hex().upper()}",
            "artifact_version": "1.0.0",
            "schema_version": "1.0.0",
            "standards_version": "3ls-v1",
            "trace_id": f"TRC-{os.urandom(8).hex().upper()}",
            "created_at": now,
            "owner_system": "REL",
            "rolled_back_artifact": artifact_id,
            "revert_steps": revert_steps,
            "timestamp": now,
        }
