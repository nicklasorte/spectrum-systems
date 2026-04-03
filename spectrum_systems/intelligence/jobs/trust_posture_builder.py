from __future__ import annotations

from typing import Any, Dict, Iterable


def build_trust_posture(signal_ids: Iterable[str], degraded: bool) -> Dict[str, Any]:
    posture = "degraded" if degraded else "stable"
    return {
        "artifact_type": "trust_posture_snapshot",
        "schema_version": "1.0.0",
        "snapshot_id": "tps-" + f"{abs(hash((tuple(signal_ids), posture))) & ((1<<64)-1):016x}",
        "signals": sorted(str(s) for s in signal_ids),
        "posture": posture,
        "created_at": "2026-01-01T00:00:00Z",
    }
