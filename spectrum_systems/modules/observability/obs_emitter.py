"""OBS: Observability record emitter.

Every governed execution must emit an obs_record containing:
trace_id, artifact_ids, duration_ms, cost_tokens.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict, List


class OBSEmitter:
    """Emits structured obs_record artifacts for governed executions."""

    def emit_obs_record(
        self,
        trace_id: str,
        artifact_ids: List[str],
        duration_ms: int,
        cost_tokens: int,
    ) -> Dict:
        """Emit and return an obs_record artifact.

        Fails-closed: raises ValueError on missing required fields.
        """
        if not trace_id:
            raise ValueError("obs_record: trace_id is required")
        if duration_ms < 0:
            raise ValueError("obs_record: duration_ms must be non-negative")
        if cost_tokens < 0:
            raise ValueError("obs_record: cost_tokens must be non-negative")

        now = datetime.now(timezone.utc).isoformat()
        record = {
            "artifact_type": "obs_record",
            "artifact_id": f"OBS-{os.urandom(4).hex().upper()}",
            "artifact_version": "1.0.0",
            "schema_version": "1.0.0",
            "standards_version": "3ls-v1",
            "trace_id": trace_id,
            "created_at": now,
            "owner_system": "OBS",
            "artifact_ids": artifact_ids,
            "duration_ms": duration_ms,
            "cost_tokens": cost_tokens,
            "timestamp": now,
        }
        return record
