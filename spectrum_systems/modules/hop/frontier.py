"""Pareto frontier construction for HOP harness scores.

Objectives (5):
- ``score`` (maximize)
- ``cost`` (minimize)
- ``latency_ms`` (minimize)
- ``trace_completeness`` (maximize)
- ``eval_coverage`` (maximize)

A point ``a`` dominates ``b`` iff for every objective ``a`` is at least as
good and ``a`` is strictly better on at least one objective.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace

OBJECTIVES: tuple[dict[str, str], ...] = (
    {"name": "score", "direction": "maximize"},
    {"name": "cost", "direction": "minimize"},
    {"name": "latency_ms", "direction": "minimize"},
    {"name": "trace_completeness", "direction": "maximize"},
    {"name": "eval_coverage", "direction": "maximize"},
)


def _dominates(a: Mapping[str, float], b: Mapping[str, float]) -> bool:
    strictly_better = False
    for obj in OBJECTIVES:
        name = obj["name"]
        if obj["direction"] == "maximize":
            if a[name] < b[name]:
                return False
            if a[name] > b[name]:
                strictly_better = True
        else:
            if a[name] > b[name]:
                return False
            if a[name] < b[name]:
                strictly_better = True
    return strictly_better


def _project(score: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": score["candidate_id"],
        "run_id": score["run_id"],
        "score_artifact_id": score["artifact_id"],
        "score": float(score["score"]),
        "cost": float(score["cost"]),
        "latency_ms": float(score["latency_ms"]),
        "trace_completeness": float(score["trace_completeness"]),
        "eval_coverage": float(score["eval_coverage"]),
    }


def compute_frontier(scores: Iterable[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], int, int]:
    """Return ``(non_dominated, dominated_count, considered_count)``."""
    points = [_project(s) for s in scores]
    considered = len(points)
    non_dominated: list[dict[str, Any]] = []
    for i, point in enumerate(points):
        is_dominated = False
        for j, other in enumerate(points):
            if i == j:
                continue
            if _dominates(other, point):
                is_dominated = True
                break
        if not is_dominated:
            non_dominated.append(point)

    # Stable de-dupe by score_artifact_id (a single score should not appear twice).
    seen_ids: set[str] = set()
    unique_non_dominated: list[dict[str, Any]] = []
    for p in non_dominated:
        if p["score_artifact_id"] in seen_ids:
            continue
        seen_ids.add(p["score_artifact_id"])
        unique_non_dominated.append(p)

    unique_non_dominated.sort(
        key=lambda p: (-p["score"], p["cost"], p["latency_ms"], p["candidate_id"])
    )
    dominated = considered - len(unique_non_dominated)
    return unique_non_dominated, dominated, considered


def build_frontier_artifact(
    scores: Iterable[Mapping[str, Any]],
    *,
    frontier_id: str,
    trace_id: str = "hop_frontier",
) -> dict[str, Any]:
    members, dominated_count, considered_count = compute_frontier(scores)
    payload: dict[str, Any] = {
        "artifact_type": "hop_harness_frontier",
        "schema_ref": "hop/harness_frontier.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary=trace_id),
        "frontier_id": frontier_id,
        "generated_at": datetime.now(tz=timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z"),
        "objectives": list(OBJECTIVES),
        "members": members,
        "dominated_count": dominated_count,
        "considered_count": considered_count,
    }
    finalize_artifact(payload, id_prefix="hop_frontier_")
    return payload
