"""Frontier streaming tests — chunked Pareto + invalid-member rejection."""

from __future__ import annotations

import math

import pytest

from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace
from spectrum_systems.modules.hop.frontier import (
    DEFAULT_WINDOW_SIZE,
    FrontierResult,
    build_frontier_artifact,
    compute_frontier,
    compute_frontier_streaming,
    iter_invalid_members,
)
from spectrum_systems.modules.hop.schemas import validate_hop_artifact


def _score(*, candidate_id, run_id, score, cost, latency_ms,
           trace_completeness=1.0, eval_coverage=1.0):
    """Build a score-shaped *payload* directly (no schema validation).

    The frontier intentionally tolerates adversarial inputs (NaN / OOB),
    so the helper bypasses the artifact finalizer when the value is
    non-finite — finalize_artifact would otherwise crash before we ever
    feed the score to the frontier.
    """
    safe_score = score if isinstance(score, float) and not math.isfinite(score) else score
    if isinstance(safe_score, float) and not math.isfinite(safe_score):
        pass_count = 0
    else:
        try:
            pass_count = int(round(float(safe_score) * 10))
        except (TypeError, ValueError):
            pass_count = 0
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
        "pass_count": max(pass_count, 0),
        "fail_count": max(10 - pass_count, 0),
        "case_count": 10,
        "aggregate_method": "pass_rate",
        "breakdown": [],
        "cost": cost,
        "latency_ms": latency_ms,
        "trace_completeness": trace_completeness,
        "eval_coverage": eval_coverage,
        "created_at": "2026-04-25T00:00:00.000000Z",
    }
    # Synthesize an artifact_id without recomputing the canonical hash on
    # NaN-bearing payloads (canonical_json would still serialize, but the
    # finalizer emits a deterministic id we don't actually need here).
    payload["artifact_id"] = f"hop_score_{candidate_id}_{run_id}"
    payload["content_hash"] = "sha256:" + "0" * 64
    return payload


def test_streaming_matches_in_memory() -> None:
    """Streaming + chunked merge yields the same frontier as the brute force pass."""
    rng_scores = [
        _score(
            candidate_id=f"c{i}",
            run_id=f"r{i}",
            score=(i % 7) / 10.0,
            cost=10 + (i % 3),
            latency_ms=5 + (i % 5),
            trace_completeness=1.0,
            eval_coverage=1.0,
        )
        for i in range(50)
    ]
    streamed = compute_frontier_streaming(rng_scores, window_size=4)
    in_memory_members, in_memory_dom, in_memory_considered = compute_frontier(
        rng_scores, window_size=10_000
    )
    assert {m["candidate_id"] for m in streamed.members} == {
        m["candidate_id"] for m in in_memory_members
    }
    assert streamed.considered_count == in_memory_considered
    assert streamed.dominated_count + streamed.invalid_count == in_memory_dom


def test_nan_score_is_dropped() -> None:
    bad = _score(
        candidate_id="bad", run_id="rb",
        score=float("nan"), cost=10, latency_ms=10,
    )
    good = _score(
        candidate_id="good", run_id="rg",
        score=0.9, cost=10, latency_ms=10,
    )
    result = compute_frontier_streaming([bad, good])
    assert result.invalid_count == 1
    assert any(m["candidate_id"] == "good" for m in result.members)
    assert all(m["candidate_id"] != "bad" for m in result.members)


def test_negative_cost_is_dropped() -> None:
    bad = _score(
        candidate_id="negcost", run_id="rb",
        score=0.9, cost=-1.0, latency_ms=10,
    )
    result = compute_frontier_streaming([bad])
    assert result.invalid_count == 1
    assert result.members == []


def test_out_of_bound_completeness_is_dropped() -> None:
    bad = _score(
        candidate_id="oob", run_id="rb",
        score=0.5, cost=10, latency_ms=10,
        trace_completeness=2.0,
    )
    result = compute_frontier_streaming([bad])
    assert result.invalid_count == 1


def test_inf_objective_is_dropped() -> None:
    bad = _score(
        candidate_id="inf", run_id="rb",
        score=0.5, cost=10, latency_ms=float("inf"),
    )
    result = compute_frontier_streaming([bad])
    assert result.invalid_count == 1


def test_zero_window_raises() -> None:
    with pytest.raises(ValueError):
        compute_frontier_streaming([], window_size=0)


def test_streaming_preserves_dedup() -> None:
    a = _score(candidate_id="a", run_id="ra", score=0.9, cost=10, latency_ms=10)
    result = compute_frontier_streaming([a, a, a], window_size=2)
    assert len(result.members) == 1


def test_iter_invalid_members_yields_dropped() -> None:
    bad = _score(candidate_id="bad", run_id="rb",
                 score=float("nan"), cost=10, latency_ms=10)
    good = _score(candidate_id="good", run_id="rg",
                  score=0.9, cost=10, latency_ms=10)
    invalid = list(iter_invalid_members([bad, good]))
    assert len(invalid) == 1
    assert invalid[0]["candidate_id"] == "bad"


def test_build_frontier_artifact_validates_with_streaming() -> None:
    a = _score(candidate_id="a", run_id="ra", score=0.9, cost=10, latency_ms=10)
    b = _score(candidate_id="b", run_id="rb", score=float("nan"), cost=10, latency_ms=10)
    payload = build_frontier_artifact([a, b], frontier_id="frontier_invalid", window_size=2)
    validate_hop_artifact(payload, "hop_harness_frontier")
    # The invalid member is folded into dominated_count for backwards
    # compatibility with the BATCH-1 contract.
    assert payload["considered_count"] == 2
    assert payload["dominated_count"] == 1


def test_streaming_handles_large_window_size() -> None:
    scores = [
        _score(
            candidate_id=f"c{i}", run_id=f"r{i}",
            score=(i % 11) / 11.0,
            cost=10.0,
            latency_ms=5.0 + i,
        )
        for i in range(200)
    ]
    result = compute_frontier_streaming(scores, window_size=1024)
    assert result.considered_count == 200
    assert result.invalid_count == 0
