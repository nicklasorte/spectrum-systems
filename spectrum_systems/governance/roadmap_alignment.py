"""PRG: Roadmap alignment record producer.

Links each roadmap step to a set of SLIs it improves and control loops it strengthens.
Emits a roadmap_alignment_record artifact.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SLIS_IMPROVED = [
    "eval_pass_rate",
    "lineage_completeness",
    "drift_rate",
    "override_age",
]

DEFAULT_CONTROL_LOOPS = [
    "admission_gate",
    "promotion_gate",
    "replay_verification",
]


def emit_roadmap_alignment_record(roadmap_path: Optional[Path] = None) -> Dict:
    """Load the 3LS roadmap and emit a roadmap_alignment_record artifact."""
    rpath = roadmap_path or (REPO_ROOT / "docs" / "governance" / "cdx_02_3ls_roadmap.json")

    steps: List[Dict] = []
    if rpath.exists():
        data = json.loads(rpath.read_text())
        raw_steps = data.get("steps", data.get("phases", []))
        for step in raw_steps:
            steps.append({
                "step_id": step.get("id", step.get("phase", "?")),
                "title": step.get("title", step.get("name", "?")),
                "owner": step.get("owner", "PRG"),
                "slis_improved": DEFAULT_SLIS_IMPROVED,
                "control_loops_strengthened": DEFAULT_CONTROL_LOOPS,
            })

    now = datetime.now(timezone.utc).isoformat()
    return {
        "artifact_type": "roadmap_alignment_record",
        "artifact_id": f"RMA-{os.urandom(4).hex().upper()}",
        "artifact_version": "1.0.0",
        "schema_version": "1.0.0",
        "standards_version": "3ls-v1",
        "trace_id": f"TRC-{os.urandom(8).hex().upper()}",
        "created_at": now,
        "owner_system": "PRG",
        "timestamp": now,
        "roadmap_items": steps,
    }
