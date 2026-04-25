"""Trace-diff miner tests — structured diff classification + invariants."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace
from spectrum_systems.modules.hop.schemas import validate_hop_artifact
from spectrum_systems.modules.hop.trace_diff import (
    TraceDiffError,
    TraceDiffInputs,
    compute_trace_diff,
)


def _score(
    *,
    candidate_id: str,
    run_id: str,
    breakdown: list[dict],
    score: float = 0.5,
    cost: float = 100.0,
    latency_ms: float = 10.0,
    trace_completeness: float = 1.0,
    eval_coverage: float = 1.0,
    eval_set_id: str = "es",
    eval_set_version: str = "1.0.0",
) -> dict:
    payload = {
        "artifact_type": "hop_harness_score",
        "schema_ref": "hop/harness_score.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary="t"),
        "run_id": run_id,
        "candidate_id": candidate_id,
        "eval_set_id": eval_set_id,
        "eval_set_version": eval_set_version,
        "score": score,
        "pass_count": sum(1 for b in breakdown if b["passed"]),
        "fail_count": sum(1 for b in breakdown if not b["passed"]),
        "case_count": len(breakdown),
        "aggregate_method": "pass_rate",
        "breakdown": breakdown,
        "cost": cost,
        "latency_ms": latency_ms,
        "trace_completeness": trace_completeness,
        "eval_coverage": eval_coverage,
        "created_at": "2026-04-25T00:00:00.000000Z",
    }
    finalize_artifact(payload, id_prefix="hop_score_")
    return payload


def _trace(*, run_id: str, candidate_id: str, case_id: str, complete: bool, output_hash=None) -> dict:
    payload = {
        "artifact_type": "hop_harness_trace",
        "schema_ref": "hop/harness_trace.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary="t"),
        "run_id": run_id,
        "candidate_id": candidate_id,
        "eval_case_id": case_id,
        "started_at": "2026-04-25T00:00:00.000000Z",
        "completed_at": "2026-04-25T00:00:00.100000Z",
        "complete": complete,
        "input_hash": "sha256:" + "a" * 64,
        "output_hash": output_hash,
        "steps": [],
        "incomplete_reason": None if complete else "test",
    }
    finalize_artifact(payload, id_prefix="hop_trace_")
    return payload


def test_diff_classifies_each_case() -> None:
    baseline = _score(
        candidate_id="base",
        run_id="rb",
        breakdown=[
            {"eval_case_id": "c1", "passed": True, "score": 1, "latency_ms": 1, "failure_reason": None},
            {"eval_case_id": "c2", "passed": True, "score": 1, "latency_ms": 1, "failure_reason": None},
            {"eval_case_id": "c3", "passed": False, "score": 0, "latency_ms": 1, "failure_reason": "x"},
            {"eval_case_id": "c4", "passed": False, "score": 0, "latency_ms": 1, "failure_reason": "y"},
        ],
        score=0.5,
    )
    candidate = _score(
        candidate_id="cand",
        run_id="rc",
        breakdown=[
            {"eval_case_id": "c1", "passed": True, "score": 1, "latency_ms": 1, "failure_reason": None},
            {"eval_case_id": "c2", "passed": False, "score": 0, "latency_ms": 1, "failure_reason": "regress"},
            {"eval_case_id": "c3", "passed": True, "score": 1, "latency_ms": 1, "failure_reason": None},
            {"eval_case_id": "c4", "passed": False, "score": 0, "latency_ms": 1, "failure_reason": "y"},
        ],
        score=0.5,
    )
    diff = compute_trace_diff(
        TraceDiffInputs(
            baseline_score=baseline,
            candidate_score=candidate,
            baseline_traces=(),
            candidate_traces=(),
        )
    )
    validate_hop_artifact(diff, "hop_harness_trace_diff")
    kinds = {entry["eval_case_id"]: entry["kind"] for entry in diff["case_diffs"]}
    assert kinds == {
        "c1": "stable_pass",
        "c2": "regression",
        "c3": "improvement",
        "c4": "stable_fail",
    }
    # Conflicting signals because both regression and improvement present.
    assert diff["conflicting_signals"]
    # Single regression and single improvement -> isolated_changes.
    assert any(e["kind"] == "regression" for e in diff["isolated_changes"])
    assert any(e["kind"] == "improvement" for e in diff["isolated_changes"])


def test_diff_detects_shared_changes() -> None:
    baseline = _score(
        candidate_id="base",
        run_id="rb",
        breakdown=[
            {"eval_case_id": f"c{i}", "passed": True, "score": 1, "latency_ms": 1, "failure_reason": None}
            for i in range(3)
        ],
    )
    candidate = _score(
        candidate_id="cand",
        run_id="rc",
        breakdown=[
            {"eval_case_id": f"c{i}", "passed": False, "score": 0, "latency_ms": 1, "failure_reason": "r"}
            for i in range(3)
        ],
    )
    diff = compute_trace_diff(
        TraceDiffInputs(
            baseline_score=baseline,
            candidate_score=candidate,
            baseline_traces=(),
            candidate_traces=(),
        )
    )
    assert any(g["kind"] == "regression" for g in diff["shared_changes"])


def test_diff_rejects_eval_set_mismatch() -> None:
    baseline = _score(
        candidate_id="base", run_id="rb", breakdown=[],
        eval_set_id="other",
    )
    candidate = _score(candidate_id="cand", run_id="rc", breakdown=[])
    with pytest.raises(TraceDiffError):
        compute_trace_diff(
            TraceDiffInputs(
                baseline_score=baseline,
                candidate_score=candidate,
                baseline_traces=(),
                candidate_traces=(),
            )
        )


def test_diff_rejects_eval_set_version_mismatch() -> None:
    baseline = _score(
        candidate_id="base", run_id="rb", breakdown=[],
        eval_set_version="2.0.0",
    )
    candidate = _score(candidate_id="cand", run_id="rc", breakdown=[])
    with pytest.raises(TraceDiffError):
        compute_trace_diff(
            TraceDiffInputs(
                baseline_score=baseline,
                candidate_score=candidate,
                baseline_traces=(),
                candidate_traces=(),
            )
        )


def test_diff_surfaces_output_hash_mismatch() -> None:
    baseline = _score(
        candidate_id="base", run_id="rb",
        breakdown=[
            {"eval_case_id": "c1", "passed": True, "score": 1, "latency_ms": 1, "failure_reason": None}
        ],
    )
    candidate = _score(
        candidate_id="cand", run_id="rc",
        breakdown=[
            {"eval_case_id": "c1", "passed": True, "score": 1, "latency_ms": 1, "failure_reason": None}
        ],
    )
    bt = _trace(run_id="rb", candidate_id="base", case_id="c1", complete=True,
                output_hash="sha256:" + "a" * 64)
    ct = _trace(run_id="rc", candidate_id="cand", case_id="c1", complete=True,
                output_hash="sha256:" + "b" * 64)
    diff = compute_trace_diff(
        TraceDiffInputs(
            baseline_score=baseline,
            candidate_score=candidate,
            baseline_traces=(bt,),
            candidate_traces=(ct,),
        )
    )
    case = diff["case_diffs"][0]
    assert case["baseline_output_hash"] != case["candidate_output_hash"]


def test_diff_invalid_inputs_raise() -> None:
    with pytest.raises(TraceDiffError):
        compute_trace_diff({"not": "inputs"})  # type: ignore[arg-type]


def test_score_delta_is_signed() -> None:
    baseline = _score(
        candidate_id="base",
        run_id="rb",
        breakdown=[],
        score=0.6,
        cost=100.0,
        latency_ms=10.0,
    )
    candidate = _score(
        candidate_id="cand",
        run_id="rc",
        breakdown=[],
        score=0.4,
        cost=200.0,
        latency_ms=5.0,
    )
    diff = compute_trace_diff(
        TraceDiffInputs(
            baseline_score=baseline,
            candidate_score=candidate,
            baseline_traces=(),
            candidate_traces=(),
        )
    )
    assert diff["score_delta"]["score"] == pytest.approx(-0.2)
    assert diff["score_delta"]["cost"] == pytest.approx(100.0)
    assert diff["score_delta"]["latency_ms"] == pytest.approx(-5.0)
