from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from .validator import validate_artifact_shape


def _now() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _dominates(a: dict[str, float], b: dict[str, float]) -> bool:
    return (
        a["score"] >= b["score"]
        and a["trace_completeness"] >= b["trace_completeness"]
        and a["eval_coverage"] >= b["eval_coverage"]
        and a["cost"] <= b["cost"]
        and a["latency"] <= b["latency"]
        and a != b
    )


def build_frontier(candidate_metrics: list[dict[str, float]], *, trace_id: str, schema_root: Any = None) -> dict[str, Any]:
    frontier_entries = []
    for candidate in candidate_metrics:
        if not any(_dominates(other, candidate) for other in candidate_metrics):
            frontier_entries.append(candidate)
    frontier_entries = sorted(frontier_entries, key=lambda item: (-item["score"], item["latency"]))

    artifact = {
        "artifact_type": "harness_frontier",
        "artifact_id": f"hop-frontier-{trace_id}",
        "schema_ref": "hop/harness_frontier.schema.json@1.0.0",
        "trace": {"trace_id": trace_id, "timestamp": _now(), "steps": [{"name": "frontier", "status": "pass"}]},
        "content_hash": _sha(frontier_entries),
        "created_at": _now(),
        "frontier_id": f"frontier-{trace_id}",
        "objective_keys": ["score", "cost", "latency", "trace_completeness", "eval_coverage"],
        "entries": frontier_entries,
    }
    validate_artifact_shape(artifact, "harness_frontier", schema_root=schema_root)
    return artifact
