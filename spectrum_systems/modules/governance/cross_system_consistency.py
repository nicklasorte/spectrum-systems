"""CRS: Cross-artifact consistency checker.

Detects schema version mismatches between consuming and upstream artifacts.
Emits cross_system_audit_record artifacts on incompatibility.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple


class CrossSystemConsistencyChecker:
    """CRS owner: Detects schema version mismatches cross-system."""

    def check_schema_version_compatibility(
        self,
        consuming_version: str,
        upstream_version: str,
        accepted_versions: List[str],
    ) -> Tuple[bool, str]:
        """Return (compatible, reason).

        Compatible only when upstream_version appears in accepted_versions.
        """
        if upstream_version not in accepted_versions:
            return (
                False,
                f"Schema version mismatch: upstream '{upstream_version}' not in "
                f"accepted versions {accepted_versions}",
            )
        return True, f"Version '{upstream_version}' is compatible"

    def check_artifact_schema_compatibility(
        self,
        consuming_artifact: Dict,
        upstream_artifact: Dict,
    ) -> Tuple[bool, str]:
        """Check that the consuming artifact's schema accepts the upstream version."""
        consuming_version = consuming_artifact.get("schema_version", "1.0")
        upstream_version = upstream_artifact.get("schema_version", "1.0")
        accepted = consuming_artifact.get("$accepted_upstream_versions", [upstream_version])
        return self.check_schema_version_compatibility(consuming_version, upstream_version, accepted)

    def emit_cross_system_audit(
        self,
        artifact_pairs: Optional[List[Dict]] = None,
    ) -> Dict:
        """Audit artifact pairs for schema compatibility; return audit record."""
        incompatibilities: List[Dict] = []

        for pair in (artifact_pairs or []):
            consuming = pair.get("consuming", {})
            upstream = pair.get("upstream", {})
            ok, msg = self.check_artifact_schema_compatibility(consuming, upstream)
            if not ok:
                incompatibilities.append({
                    "consuming": consuming.get("artifact_id", "?"),
                    "upstream": upstream.get("artifact_id", "?"),
                    "reason": msg,
                })

        now = datetime.now(timezone.utc).isoformat()
        return {
            "artifact_type": "cross_system_audit_record",
            "artifact_id": f"CRS-AUDIT-{os.urandom(4).hex().upper()}",
            "artifact_version": "1.0.0",
            "schema_version": "1.0.0",
            "standards_version": "3ls-v1",
            "trace_id": f"TRC-{os.urandom(8).hex().upper()}",
            "created_at": now,
            "owner_system": "CRS",
            "timestamp": now,
            "incompatibilities": incompatibilities,
        }
