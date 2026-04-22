"""JSX: In-memory judgment store with supersession semantics.

retrieve_judgment() returns only active, non-superseded judgments.
Superseded judgments are stored but never returned through normal retrieval.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict, Optional

from spectrum_systems.modules.governance.judgment import validate_judgment_evidence


class JudgmentStore:
    """Active-set model for judgments with supersession tracking."""

    def __init__(self) -> None:
        self._store: Dict[str, Dict] = {}
        self._supersessions: Dict[str, str] = {}  # old_id → new_id

    # ── write ─────────────────────────────────────────────────────────────

    def create_judgment(self, judgment: Dict) -> Dict:
        """Create and store a judgment after evidence sufficiency check."""
        ok, msg = validate_judgment_evidence(judgment)
        if not ok:
            raise ValueError(f"Evidence insufficiency: {msg}")

        judgment.setdefault("status", "active")
        judgment.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        self._store[judgment["id"]] = judgment
        return judgment

    def supersede_judgment(
        self, old_id: str, new_id: str, reason: str
    ) -> Dict:
        """Mark old_id as superseded by new_id and record a supersession artifact."""
        old = self._store.get(old_id)
        if old is None:
            raise KeyError(f"Judgment not found: {old_id}")

        old["status"] = "superseded"
        old["superseded_by"] = new_id
        self._supersessions[old_id] = new_id

        supersession = {
            "supersession_id": f"SUP-{os.urandom(4).hex().upper()}",
            "artifact_type": "supersession_record",
            "old_judgment_id": old_id,
            "new_judgment_id": new_id,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "active",
        }
        self._store[supersession["supersession_id"]] = supersession
        return supersession

    # ── read ──────────────────────────────────────────────────────────────

    def retrieve_judgment(self, judgment_id: str) -> Optional[Dict]:
        """Return judgment only if it is active (not superseded or expired)."""
        judgment = self._store.get(judgment_id)
        if judgment is None:
            return None
        if judgment.get("status") != "active":
            return None
        if judgment_id in self._supersessions:
            return None
        return judgment

    def get(self, artifact_id: str) -> Optional[Dict]:
        return self._store.get(artifact_id)

    def list_active_judgments(self) -> list:
        return [
            j for j in self._store.values()
            if j.get("artifact_type") not in ("supersession_record",)
            and j.get("status") == "active"
        ]
