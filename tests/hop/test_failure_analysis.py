"""Failure-analysis tests — causal hypothesis structure + invariants."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace
from spectrum_systems.modules.hop.failure_analysis import (
    FailureAnalysisError,
    HypothesisInputs,
    build_failure_hypothesis,
)
from spectrum_systems.modules.hop.schemas import validate_hop_artifact
from spectrum_systems.modules.hop.trace_diff import (
    TraceDiffInputs,
    compute_trace_diff,
)
from tests.hop.conftest import make_baseline_candidate


def _score(*, candidate_id, run_id, breakdown, score=0.5):
    payload = {
        "artifact_type": "hop_harness_score",
        "schema_ref": "hop/harness_score.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary="t"),
        "run_id": run_id,
        "candidate_id": candidate_id,
        "eval_set_id": "es",
        "eval_set_version": "1.0.0",
        "score": score,
        "pass_count": sum(1 for b in breakdown if b["passed"]),
        "fail_count": sum(1 for b in breakdown if not b["passed"]),
        "case_count": len(breakdown),
        "aggregate_method": "pass_rate",
        "breakdown": breakdown,
        "cost": 100.0,
        "latency_ms": 10.0,
        "trace_completeness": 1.0,
        "eval_coverage": 1.0,
        "created_at": "2026-04-25T00:00:00.000000Z",
    }
    finalize_artifact(payload, id_prefix="hop_score_")
    return payload


def _candidate(*, candidate_id, code_source):
    payload = {
        "artifact_type": "hop_harness_candidate",
        "schema_ref": "hop/harness_candidate.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary="t"),
        "candidate_id": candidate_id,
        "harness_type": "transcript_to_faq",
        "code_module": "spectrum_systems.modules.hop.baseline_harness",
        "code_entrypoint": "run",
        "code_source": code_source,
        "declared_methods": ["run"],
        "parent_candidate_id": None,
        "tags": [],
        "created_at": "2026-04-25T00:00:00.000000Z",
    }
    finalize_artifact(payload, id_prefix="hop_candidate_")
    return payload


def _diff_for(baseline_breakdown, candidate_breakdown, baseline_score=0.5, candidate_score=0.5):
    baseline = _score(
        candidate_id="base", run_id="rb",
        breakdown=baseline_breakdown, score=baseline_score,
    )
    candidate = _score(
        candidate_id="cand", run_id="rc",
        breakdown=candidate_breakdown, score=candidate_score,
    )
    return baseline, candidate, compute_trace_diff(
        TraceDiffInputs(
            baseline_score=baseline,
            candidate_score=candidate,
            baseline_traces=(),
            candidate_traces=(),
        )
    )


def test_regression_hypothesis_validates() -> None:
    baseline_bd = [
        {"eval_case_id": "c1", "passed": True, "score": 1, "latency_ms": 1, "failure_reason": None},
    ]
    candidate_bd = [
        {"eval_case_id": "c1", "passed": False, "score": 0, "latency_ms": 1, "failure_reason": "x"},
    ]
    baseline, candidate, diff = _diff_for(baseline_bd, candidate_bd, 1.0, 0.0)
    base_c = _candidate(candidate_id="base", code_source="def run(): pass\n")
    cand_c = _candidate(candidate_id="cand", code_source="def run(): pass\n# changed\n")
    hypothesis = build_failure_hypothesis(
        HypothesisInputs(
            baseline_candidate=base_c,
            candidate=cand_c,
            trace_diff=diff,
        )
    )
    validate_hop_artifact(hypothesis, "hop_harness_failure_hypothesis")
    assert hypothesis["stage"] == "causal_analysis"
    assert hypothesis["failure_class"] == "regression"
    assert hypothesis["observed_change"] == "regression"
    assert hypothesis["baseline_candidate_id"] == "base"
    assert hypothesis["confidence"] >= 0.0


def test_improvement_hypothesis_validates() -> None:
    baseline_bd = [
        {"eval_case_id": "c1", "passed": False, "score": 0, "latency_ms": 1, "failure_reason": "x"},
    ]
    candidate_bd = [
        {"eval_case_id": "c1", "passed": True, "score": 1, "latency_ms": 1, "failure_reason": None},
    ]
    baseline, candidate, diff = _diff_for(baseline_bd, candidate_bd, 0.0, 1.0)
    base_c = _candidate(candidate_id="base", code_source="x")
    cand_c = _candidate(candidate_id="cand", code_source="x\n# improved\n")
    hypothesis = build_failure_hypothesis(
        HypothesisInputs(
            baseline_candidate=base_c,
            candidate=cand_c,
            trace_diff=diff,
        )
    )
    assert hypothesis["failure_class"] == "improvement"
    assert hypothesis["severity"] == "info"
    assert hypothesis["blocks_promotion"] is False


def test_neutral_hypothesis() -> None:
    baseline_bd = [
        {"eval_case_id": "c1", "passed": True, "score": 1, "latency_ms": 1, "failure_reason": None},
    ]
    candidate_bd = [
        {"eval_case_id": "c1", "passed": True, "score": 1, "latency_ms": 1, "failure_reason": None},
    ]
    baseline, candidate, diff = _diff_for(baseline_bd, candidate_bd, 1.0, 1.0)
    base_c = _candidate(candidate_id="base", code_source="x")
    cand_c = _candidate(candidate_id="cand", code_source="x\n# noop\n")
    hypothesis = build_failure_hypothesis(
        HypothesisInputs(
            baseline_candidate=base_c,
            candidate=cand_c,
            trace_diff=diff,
        )
    )
    assert hypothesis["observed_change"] == "neutral"
    assert hypothesis["failure_class"] == "neutral_change"


def test_suspected_cause_is_enum_like() -> None:
    """suspected_cause must come from a small structurally-derived set."""
    allowed_prefixes = {
        "shared_",
        "isolated_",
        "no_observable_",
        "conflicting_signals_present",
        "unattributed_",
    }
    baseline_bd = [
        {"eval_case_id": f"c{i}", "passed": True, "score": 1, "latency_ms": 1, "failure_reason": None}
        for i in range(3)
    ]
    candidate_bd = [
        {"eval_case_id": f"c{i}", "passed": False, "score": 0, "latency_ms": 1, "failure_reason": "r"}
        for i in range(3)
    ]
    baseline, candidate, diff = _diff_for(baseline_bd, candidate_bd, 1.0, 0.0)
    base_c = _candidate(candidate_id="base", code_source="x")
    cand_c = _candidate(candidate_id="cand", code_source="x\n# y\n")
    hypothesis = build_failure_hypothesis(
        HypothesisInputs(
            baseline_candidate=base_c,
            candidate=cand_c,
            trace_diff=diff,
        )
    )
    cause = hypothesis["suspected_cause"]
    assert any(cause.startswith(p) or cause == p for p in allowed_prefixes)


def test_mismatched_baseline_is_rejected() -> None:
    baseline_bd = [
        {"eval_case_id": "c1", "passed": True, "score": 1, "latency_ms": 1, "failure_reason": None},
    ]
    candidate_bd = [
        {"eval_case_id": "c1", "passed": False, "score": 0, "latency_ms": 1, "failure_reason": "x"},
    ]
    baseline, candidate, diff = _diff_for(baseline_bd, candidate_bd, 1.0, 0.0)
    # Tamper: swap the baseline_candidate_id reference on the diff.
    diff["baseline_candidate_id"] = "ghost_baseline"
    base_c = _candidate(candidate_id="base", code_source="x")
    cand_c = _candidate(candidate_id="cand", code_source="x\n# y\n")
    with pytest.raises(FailureAnalysisError):
        build_failure_hypothesis(
            HypothesisInputs(
                baseline_candidate=base_c,
                candidate=cand_c,
                trace_diff=diff,
            )
        )


def test_invalid_inputs_raise() -> None:
    with pytest.raises(FailureAnalysisError):
        build_failure_hypothesis({"not": "inputs"})  # type: ignore[arg-type]


def test_diff_artifact_type_must_match() -> None:
    fake_diff = {
        "artifact_type": "hop_harness_score",  # wrong type
        "diff_id": "x",
        "baseline_candidate_id": "b",
        "candidate_id": "c",
        "score_delta": {"score": 0, "cost": 0, "latency_ms": 0,
                        "trace_completeness": 0, "eval_coverage": 0},
        "case_diffs": [],
    }
    base_c = _candidate(candidate_id="b", code_source="x")
    cand_c = _candidate(candidate_id="c", code_source="x")
    with pytest.raises(FailureAnalysisError):
        build_failure_hypothesis(
            HypothesisInputs(
                baseline_candidate=base_c,
                candidate=cand_c,
                trace_diff=fake_diff,
            )
        )
