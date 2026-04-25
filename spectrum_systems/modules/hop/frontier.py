"""Pareto frontier construction for HOP harness scores.

Objectives (5):
- ``score`` (maximize)
- ``cost`` (minimize)
- ``latency_ms`` (minimize)
- ``trace_completeness`` (maximize)
- ``eval_coverage`` (maximize)

A point ``a`` dominates ``b`` iff for every objective ``a`` is at least as
good and ``a`` is strictly better on at least one objective.

BATCH-2 hardens the frontier for large stores:

* :func:`compute_frontier_streaming` consumes an iterator of score payloads
  and applies a chunk-based Pareto merge so peak memory is bounded by
  ``window_size`` projected points (≈300 bytes each — < 50 MB at the
  default window of 4096).
* The merge uses the monotone Pareto property: every member of a chunk's
  local frontier survives only if it is not dominated by any member of any
  other chunk's local frontier. Non-frontier points are discarded as soon
  as their chunk closes, so they never accumulate.
* :func:`compute_frontier` keeps the BATCH-1 in-memory API for callers
  whose input fits comfortably in memory and streams under the hood for
  parity with the chunked path.
* All members emitted by either entrypoint must individually satisfy
  :func:`_validate_member_payload` (no NaN, no out-of-range objectives,
  required fields present). Invalid scores are dropped and surfaced via
  the ``invalid_count`` field of the public result.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Iterator, Mapping

from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace

OBJECTIVES: tuple[dict[str, str], ...] = (
    {"name": "score", "direction": "maximize"},
    {"name": "cost", "direction": "minimize"},
    {"name": "latency_ms", "direction": "minimize"},
    {"name": "trace_completeness", "direction": "maximize"},
    {"name": "eval_coverage", "direction": "maximize"},
)

DEFAULT_WINDOW_SIZE = 4096
"""Default chunk size for streaming frontier computation.

Selected so that worst-case resident memory (each projected point is
≈300 bytes including dict overhead and identifier strings) stays well
under the 50 MB BATCH-2 budget even with adversarially large windows.
"""

_REQUIRED_KEYS: tuple[str, ...] = (
    "candidate_id",
    "run_id",
    "artifact_id",
    "score",
    "cost",
    "latency_ms",
    "trace_completeness",
    "eval_coverage",
)

_RANGE_BOUND_OBJECTIVES = {"score", "trace_completeness", "eval_coverage"}


@dataclass(frozen=True)
class FrontierResult:
    """Immutable summary returned by streaming frontier computation."""

    members: list[dict[str, Any]]
    dominated_count: int
    considered_count: int
    invalid_count: int


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


def _validate_member_payload(score: Mapping[str, Any]) -> bool:
    """Return True iff a score payload is a valid frontier candidate.

    Drops anything that:
    - is missing required keys;
    - has non-finite objective values (NaN / inf);
    - has a [0,1]-bounded objective outside [0,1];
    - has a negative cost or latency.

    A failed validation is silent at this layer; the caller (CLI or
    optimization loop) is expected to emit a ``frontier_invalid_member``
    failure hypothesis with the rejected ``artifact_id``.
    """
    for key in _REQUIRED_KEYS:
        if key not in score:
            return False
    try:
        for obj in OBJECTIVES:
            value = float(score[obj["name"]])
            if not math.isfinite(value):
                return False
            if obj["name"] in _RANGE_BOUND_OBJECTIVES and not (0.0 <= value <= 1.0):
                return False
            if obj["direction"] == "minimize" and value < 0.0:
                return False
    except (TypeError, ValueError):
        return False
    return True


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


def _local_frontier(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the non-dominated subset of ``points``.

    O(n^2) in the chunk size, which is bounded by ``window_size``. Two
    points with identical objectives are both retained; the dedupe pass at
    the end of the streaming function handles duplicate score artifact ids.
    """
    survivors: list[dict[str, Any]] = []
    for i, point in enumerate(points):
        dominated = False
        for j, other in enumerate(points):
            if i == j:
                continue
            if _dominates(other, point):
                dominated = True
                break
        if not dominated:
            survivors.append(point)
    return survivors


def _merge_two_frontiers(
    base: list[dict[str, Any]], incoming: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Merge two local frontiers, keeping only mutually non-dominated points."""
    if not base:
        return list(incoming)
    if not incoming:
        return list(base)
    candidates = base + incoming
    return _local_frontier(candidates)


def _dedupe_and_sort(members: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen_ids: set[str] = set()
    unique: list[dict[str, Any]] = []
    for p in members:
        sid = p["score_artifact_id"]
        if sid in seen_ids:
            continue
        seen_ids.add(sid)
        unique.append(p)
    unique.sort(
        key=lambda p: (-p["score"], p["cost"], p["latency_ms"], p["candidate_id"])
    )
    return unique


def compute_frontier_streaming(
    scores: Iterable[Mapping[str, Any]],
    *,
    window_size: int = DEFAULT_WINDOW_SIZE,
) -> FrontierResult:
    """Streaming chunked Pareto frontier.

    Memory is bounded by ``window_size`` projected points plus the running
    frontier. Invalid score payloads are dropped and surfaced via
    ``invalid_count``.
    """
    if window_size <= 0:
        raise ValueError(f"hop_frontier_invalid_window:{window_size}")

    considered = 0
    invalid = 0
    running_frontier: list[dict[str, Any]] = []
    chunk: list[dict[str, Any]] = []

    for score in scores:
        considered += 1
        if not _validate_member_payload(score):
            invalid += 1
            continue
        chunk.append(_project(score))
        if len(chunk) >= window_size:
            local = _local_frontier(chunk)
            running_frontier = _merge_two_frontiers(running_frontier, local)
            chunk = []

    if chunk:
        local = _local_frontier(chunk)
        running_frontier = _merge_two_frontiers(running_frontier, local)

    members = _dedupe_and_sort(running_frontier)
    dominated = max(considered - invalid - len(members), 0)
    return FrontierResult(
        members=members,
        dominated_count=dominated,
        considered_count=considered,
        invalid_count=invalid,
    )


def compute_frontier(
    scores: Iterable[Mapping[str, Any]],
    *,
    window_size: int = DEFAULT_WINDOW_SIZE,
) -> tuple[list[dict[str, Any]], int, int]:
    """Return ``(non_dominated, dominated_count, considered_count)``.

    Backward-compatible entrypoint preserved for BATCH-1 callers. Uses the
    streaming path internally; ``invalid_count`` is folded into the
    dominated count for parity with the BATCH-1 contract — invalid scores
    were already silently excluded in BATCH-1.
    """
    result = compute_frontier_streaming(scores, window_size=window_size)
    dominated = result.dominated_count + result.invalid_count
    return result.members, dominated, result.considered_count


def iter_invalid_members(scores: Iterable[Mapping[str, Any]]) -> Iterator[dict[str, Any]]:
    """Yield score payloads that fail :func:`_validate_member_payload`.

    Used by the optimization loop / CLI to emit ``frontier_invalid_member``
    failure hypotheses without re-implementing validation rules.
    """
    for score in scores:
        if not _validate_member_payload(score):
            yield dict(score)


def build_frontier_artifact(
    scores: Iterable[Mapping[str, Any]],
    *,
    frontier_id: str,
    trace_id: str = "hop_frontier",
    window_size: int = DEFAULT_WINDOW_SIZE,
) -> dict[str, Any]:
    result = compute_frontier_streaming(scores, window_size=window_size)
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
        "members": result.members,
        "dominated_count": result.dominated_count + result.invalid_count,
        "considered_count": result.considered_count,
    }
    finalize_artifact(payload, id_prefix="hop_frontier_")
    return payload
