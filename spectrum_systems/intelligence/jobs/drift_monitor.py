from __future__ import annotations

from typing import Dict, Any


def build_drift_signal(*, signal_id: str, artifact_family: str, severity: str = "medium") -> Dict[str, Any]:
    return {
        "artifact_type": "drift_signal_record",
        "schema_version": "1.0.0",
        "signal_id": signal_id,
        "signal_type": "quality",
        "artifact_family": artifact_family,
        "severity": severity,
        "created_at": "2026-01-01T00:00:00Z",
    }
