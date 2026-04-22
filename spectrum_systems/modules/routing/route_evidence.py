"""ROU: Route evidence tracking.

Every routing decision must emit a route_record artifact capturing
from/to systems, the artifact being routed, and the routing reason.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict


class RouteEvidenceEmitter:
    """Emits route_record artifacts for every inter-system routing decision."""

    def route_artifact(
        self,
        from_system: str,
        to_system: str,
        routed_artifact_id: str,
        reason: str,
        trace_id: str | None = None,
    ) -> Dict:
        """Route an artifact and emit an evidence record.

        Returns the route_record artifact dict.
        """
        if not from_system or not to_system:
            raise ValueError("route_record: from_system and to_system are required")
        if not routed_artifact_id:
            raise ValueError("route_record: routed_artifact_id is required")
        if not reason:
            raise ValueError("route_record: reason is required")

        now = datetime.now(timezone.utc).isoformat()
        record = {
            "artifact_type": "route_record",
            "artifact_id": f"RTE-{os.urandom(4).hex().upper()}",
            "artifact_version": "1.0.0",
            "schema_version": "1.0.0",
            "standards_version": "3ls-v1",
            "trace_id": trace_id or f"TRC-{os.urandom(8).hex().upper()}",
            "created_at": now,
            "owner_system": "ROU",
            "from_system": from_system,
            "to_system": to_system,
            "routed_artifact_id": routed_artifact_id,
            "reason": reason,
            "timestamp": now,
        }
        return record
