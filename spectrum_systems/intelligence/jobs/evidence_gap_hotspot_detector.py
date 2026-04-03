from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable


def detect_evidence_gaps(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    counter = Counter(str(r.get("artifact_family", "unknown")) for r in records if not r.get("has_evidence", False))
    return {
        "artifact_type": "evidence_gap_hotspot_report",
        "schema_version": "1.0.0",
        "report_id": "egh-" + f"{abs(hash(tuple(counter.items()))) & ((1<<64)-1):016x}",
        "hotspots": [
            {"artifact_family": fam, "missing_evidence_count": count}
            for fam, count in counter.most_common()
        ],
    }
