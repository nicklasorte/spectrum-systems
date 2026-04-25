"""Frontier tests — Pareto dominance and artifact emission."""

from __future__ import annotations

from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace
from spectrum_systems.modules.hop.frontier import (
    OBJECTIVES,
    build_frontier_artifact,
    compute_frontier,
)
from spectrum_systems.modules.hop.schemas import validate_hop_artifact


def _score(*, candidate_id, run_id, score, cost, latency_ms, trace_completeness, eval_coverage):
    payload = {
        "artifact_type": "hop_harness_score",
        "schema_ref": "hop/harness_score.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary="t"),
        "run_id": run_id,
        "candidate_id": candidate_id,
        "eval_set_id": "x",
        "eval_set_version": "1.0.0",
        "score": score,
        "pass_count": int(round(score * 10)),
        "fail_count": 10 - int(round(score * 10)),
        "case_count": 10,
        "aggregate_method": "pass_rate",
        "breakdown": [],
        "cost": cost,
        "latency_ms": latency_ms,
        "trace_completeness": trace_completeness,
        "eval_coverage": eval_coverage,
        "created_at": "2026-04-25T00:00:00.000000Z",
    }
    finalize_artifact(payload, id_prefix="hop_score_")
    return payload


def test_strictly_dominated_point_is_excluded() -> None:
    a = _score(
        candidate_id="a",
        run_id="ra",
        score=0.9,
        cost=10,
        latency_ms=10,
        trace_completeness=1.0,
        eval_coverage=1.0,
    )
    b = _score(
        candidate_id="b",
        run_id="rb",
        score=0.5,
        cost=20,
        latency_ms=20,
        trace_completeness=0.5,
        eval_coverage=0.5,
    )
    members, dominated, considered = compute_frontier([a, b])
    assert considered == 2
    assert dominated == 1
    ids = {m["candidate_id"] for m in members}
    assert ids == {"a"}


def test_non_dominated_points_are_kept() -> None:
    a = _score(
        candidate_id="a",
        run_id="ra",
        score=0.9,
        cost=20,
        latency_ms=20,
        trace_completeness=1.0,
        eval_coverage=1.0,
    )
    b = _score(
        candidate_id="b",
        run_id="rb",
        score=0.7,
        cost=5,
        latency_ms=5,
        trace_completeness=1.0,
        eval_coverage=1.0,
    )
    members, dominated, considered = compute_frontier([a, b])
    assert considered == 2
    assert dominated == 0
    ids = {m["candidate_id"] for m in members}
    assert ids == {"a", "b"}


def test_frontier_artifact_validates() -> None:
    score = _score(
        candidate_id="a",
        run_id="ra",
        score=0.9,
        cost=10,
        latency_ms=10,
        trace_completeness=1.0,
        eval_coverage=1.0,
    )
    payload = build_frontier_artifact([score], frontier_id="frontier_test")
    validate_hop_artifact(payload, "hop_harness_frontier")
    assert payload["objectives"] == list(OBJECTIVES)
    assert payload["considered_count"] == 1
    assert payload["dominated_count"] == 0


def test_empty_input_yields_empty_frontier() -> None:
    members, dominated, considered = compute_frontier([])
    assert members == []
    assert dominated == 0
    assert considered == 0
