"""Evaluator tests — runs, scores, traces, and fail-closed behavior."""

from __future__ import annotations

import pytest

from spectrum_systems.modules.hop.evaluator import EvalSet, evaluate_candidate
from spectrum_systems.modules.hop.schemas import (
    HopSchemaError,
    validate_hop_artifact,
)
from tests.hop.conftest import make_baseline_candidate


def test_baseline_runs_against_full_eval_set(eval_set: EvalSet, store) -> None:
    candidate = make_baseline_candidate()
    result = evaluate_candidate(
        candidate_payload=candidate,
        eval_set=eval_set,
        store=store,
    )
    score = result["score"]
    validate_hop_artifact(score, "hop_harness_score")
    validate_hop_artifact(result["run"], "hop_harness_run")
    assert result["run"]["status"] == "completed"
    assert score["case_count"] == eval_set.case_count
    assert score["pass_count"] + score["fail_count"] == eval_set.case_count
    # Baseline must beat 0 on goldens — sanity floor.
    assert score["score"] > 0.5


def test_each_case_produces_a_trace(eval_set: EvalSet, store) -> None:
    candidate = make_baseline_candidate()
    result = evaluate_candidate(
        candidate_payload=candidate,
        eval_set=eval_set,
        store=store,
    )
    assert len(result["traces"]) == eval_set.case_count
    for trace in result["traces"]:
        validate_hop_artifact(trace, "hop_harness_trace")


def test_runtime_error_is_caught_and_emits_failure(eval_set: EvalSet, store) -> None:
    candidate = make_baseline_candidate(
        code_source="def run(_):\n    raise RuntimeError('boom')\n"
    )

    result = evaluate_candidate(
        candidate_payload=candidate,
        eval_set=eval_set,
        store=store,
    )
    assert result["run"]["status"] == "completed"
    assert result["score"]["score"] == 0.0
    assert all(f["failure_class"] == "runtime_error" for f in result["failures"])
    assert len(result["failures"]) == eval_set.case_count


def test_malformed_output_is_classified(eval_set: EvalSet, store) -> None:
    candidate = make_baseline_candidate(
        code_source="def run(_):\n    return {'not': 'valid'}\n"
    )

    result = evaluate_candidate(
        candidate_payload=candidate,
        eval_set=eval_set,
        store=store,
    )
    assert any(f["failure_class"] == "malformed_artifact" for f in result["failures"])


def test_evaluator_rejects_invalid_candidate(eval_set: EvalSet) -> None:
    with pytest.raises(HopSchemaError):
        evaluate_candidate(
            candidate_payload={"artifact_type": "hop_harness_candidate"},
                eval_set=eval_set,
        )


def test_evaluator_rejects_empty_eval_set() -> None:
    candidate = make_baseline_candidate()
    empty_set = EvalSet(eval_set_id="x", eval_set_version="1.0.0", cases=())
    with pytest.raises(ValueError, match="empty_eval_set"):
        evaluate_candidate(
            candidate_payload=candidate,
                eval_set=empty_set,
        )


def test_evaluator_does_not_modify_candidate(eval_set: EvalSet, store) -> None:
    candidate = make_baseline_candidate()
    original = dict(candidate)
    evaluate_candidate(
        candidate_payload=candidate,
        eval_set=eval_set,
        store=store,
    )
    assert candidate == original
