from __future__ import annotations

from collections import Counter
from typing import Dict, Iterable, Any


def detect_override_hotspots(events: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    counter = Counter(str(e.get("policy_key", "unknown")) for e in events if e.get("overridden", False))
    hotspots = [{"key": key, "count": count} for key, count in counter.most_common()]
    return {
        "artifact_type": "override_hotspot_report",
        "schema_version": "1.0.0",
        "report_id": "ohr-" + f"{abs(hash(tuple(counter.items()))) & ((1<<64)-1):016x}",
        "hotspots": hotspots,
    }
