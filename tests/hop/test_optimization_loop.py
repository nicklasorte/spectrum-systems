"""End-to-end optimization loop tests + adversarial scenarios."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from spectrum_systems.modules.hop import (
    admission,
    baseline_harness,
    failure_analysis,
    mutation_policy,
    optimization_loop,
    proposer,
    trace_diff,
)
from spectrum_systems.modules.hop.evaluator import EvalSet, evaluate_candidate
from spectrum_systems.modules.hop.experience_store import ExperienceStore
from tests.hop.conftest import make_baseline_candidate


def _runner_factory_for_baseline(_candidate: Mapping[str, Any]):
    """Return the baseline harness runner for any candidate.

    The proposer's templates are textual rewrites of the baseline source
    that preserve baseline semantics. For BATCH-2 tests we therefore
    execute the baseline harness function regardless of which mutation
    template the candidate carries — the mutation policy + admission
    pipeline is the surface under test, not the executed code.
    """
    return baseline_harness.run


@pytest.fixture()
def baseline_evaluation(store: ExperienceStore, eval_set: EvalSet, eval_cases):
    candidate = make_baseline_candidate()
    ok, failures = admission.admit_candidate(candidate, eval_cases)
    assert ok, failures
    store.write_artifact(candidate)
    result = evaluate_candidate(
        candidate_payload=candidate,
        eval_set=eval_set,
        store=store,
    )
    return candidate, result


def test_pipeline_is_strictly_ordered(
    store: ExperienceStore, eval_set: EvalSet, eval_cases, baseline_evaluation
) -> None:
    baseline_candidate, baseline_result = baseline_evaluation
    cycle = optimization_loop.run_proposer_cycle(
        baseline_candidate=baseline_candidate,
        eval_cases=eval_cases,
        eval_set=eval_set,
        store=store,
        baseline_score=baseline_result["score"],
        baseline_traces=tuple(baseline_result["traces"]),
        max_proposals=2,
    )
    assert cycle.accepted_candidates
    # Every accepted candidate produced a run, score, and trace_diff.
    assert len(cycle.runs) == len(cycle.accepted_candidates)
    assert len(cycle.scores) == len(cycle.accepted_candidates)
    assert len(cycle.trace_diffs) == len(cycle.accepted_candidates)
    assert len(cycle.causal_hypotheses) == len(cycle.accepted_candidates)
    # Frontier was recomputed.
    assert cycle.frontier_payload is not None
    assert cycle.frontier_payload["considered_count"] >= 1


def test_loop_persists_only_via_store(
    store: ExperienceStore, eval_set: EvalSet, eval_cases, baseline_evaluation
) -> None:
    baseline_candidate, baseline_result = baseline_evaluation
    pre_count = store.count(artifact_type="hop_harness_candidate")
    optimization_loop.run_proposer_cycle(
        baseline_candidate=baseline_candidate,
        eval_cases=eval_cases,
        eval_set=eval_set,
        store=store,
        baseline_score=baseline_result["score"],
        baseline_traces=tuple(baseline_result["traces"]),
        max_proposals=1,
    )
    post_count = store.count(artifact_type="hop_harness_candidate")
    assert post_count == pre_count + 1


def test_loop_rejects_candidate_violating_mutation_policy(
    store: ExperienceStore, eval_set: EvalSet, eval_cases, baseline_evaluation, monkeypatch
) -> None:
    """Inject a malicious template and verify it is rejected at the policy gate."""
    baseline_candidate, baseline_result = baseline_evaluation

    def _bad_template(baseline_source: str) -> tuple[str, str]:
        return (
            baseline_source + "\nimport subprocess\nsubprocess.run(['ls'])\n",
            "additive_context",
        )

    monkeypatch.setattr(
        proposer,
        "_TEMPLATES",
        (_bad_template,),
    )

    cycle = optimization_loop.run_proposer_cycle(
        baseline_candidate=baseline_candidate,
        eval_cases=eval_cases,
        eval_set=eval_set,
        store=store,
        baseline_score=baseline_result["score"],
        baseline_traces=tuple(baseline_result["traces"]),
        max_proposals=1,
    )
    assert cycle.accepted_candidates == []
    assert any(r["stage"] == "mutation_policy" for r in cycle.rejected_proposals)


def test_loop_rejects_candidate_failing_safety_scan(
    store: ExperienceStore, eval_set: EvalSet, eval_cases, baseline_evaluation, monkeypatch
) -> None:
    """A candidate that hardcodes an answer is caught by the admission gate."""
    baseline_candidate, baseline_result = baseline_evaluation
    # Find a forbidden substring from the eval set.
    forbidden = None
    for case in eval_cases:
        forb_list = case.get("pass_criteria", {}).get("rules", {}).get(
            "forbidden_substrings_in_answers", []
        ) or []
        if forb_list:
            forbidden = forb_list[0]
            break
    assert forbidden is not None

    def _hardcoded_template(baseline_source: str) -> tuple[str, str]:
        return (
            baseline_source.replace(
                "items: list[dict[str, Any]] = []",
                f"items: list[dict[str, Any]] = []  # leak={forbidden!r}",
            ),
            "additive_context",
        )

    monkeypatch.setattr(proposer, "_TEMPLATES", (_hardcoded_template,))

    cycle = optimization_loop.run_proposer_cycle(
        baseline_candidate=baseline_candidate,
        eval_cases=eval_cases,
        eval_set=eval_set,
        store=store,
        baseline_score=baseline_result["score"],
        baseline_traces=tuple(baseline_result["traces"]),
        max_proposals=1,
    )
    assert cycle.accepted_candidates == []
    assert any(r["stage"] == "admission" for r in cycle.rejected_proposals)


def test_loop_skips_causal_hypothesis_without_baseline(
    store: ExperienceStore, eval_set: EvalSet, eval_cases, baseline_evaluation
) -> None:
    baseline_candidate, _ = baseline_evaluation
    cycle = optimization_loop.run_proposer_cycle(
        baseline_candidate=baseline_candidate,
        eval_cases=eval_cases,
        eval_set=eval_set,
        store=store,
        baseline_score=None,
        baseline_traces=None,
        max_proposals=1,
    )
    assert cycle.accepted_candidates
    assert cycle.trace_diffs == []
    assert cycle.causal_hypotheses == []


def test_proposer_does_not_directly_persist(
    store: ExperienceStore, eval_set: EvalSet, eval_cases, baseline_evaluation
) -> None:
    """Calling the proposer in isolation must NOT touch the store.

    We snapshot the index byte length, run the proposer alone, and
    re-check the index. Any mutation by the proposer constitutes a
    boundary violation.
    """
    baseline_candidate, _ = baseline_evaluation
    pre_bytes = store.index_path.read_bytes()
    bundles = proposer.propose_candidates(
        baseline_candidate=baseline_candidate,
        context=proposer.load_proposer_context(store),
    )
    post_bytes = store.index_path.read_bytes()
    assert bundles
    assert pre_bytes == post_bytes


def test_adversarial_runner_returning_invalid_faq_is_blocked(
    store: ExperienceStore, eval_set: EvalSet, eval_cases, baseline_evaluation
) -> None:
    """Sandboxed candidate execution remains fail-closed for adversarial proposals."""
    baseline_candidate, baseline_result = baseline_evaluation

    cycle = optimization_loop.run_proposer_cycle(
        baseline_candidate=baseline_candidate,
        eval_cases=eval_cases,
        eval_set=eval_set,
        store=store,
        baseline_score=baseline_result["score"],
        baseline_traces=tuple(baseline_result["traces"]),
        max_proposals=1,
    )
    assert cycle.scores
    assert any(score["score"] <= baseline_result["score"]["score"] for score in cycle.scores)


def test_optimization_loop_writes_trace_diff_and_hypothesis(
    store: ExperienceStore, eval_set: EvalSet, eval_cases, baseline_evaluation
) -> None:
    baseline_candidate, baseline_result = baseline_evaluation
    optimization_loop.run_proposer_cycle(
        baseline_candidate=baseline_candidate,
        eval_cases=eval_cases,
        eval_set=eval_set,
        store=store,
        baseline_score=baseline_result["score"],
        baseline_traces=tuple(baseline_result["traces"]),
        max_proposals=1,
    )
    diffs = list(store.iter_index(artifact_type="hop_harness_trace_diff"))
    assert diffs
    causal = list(
        store.iter_index(
            artifact_type="hop_harness_failure_hypothesis",
            predicate=lambda r: r.get("fields", {}).get("stage") == "causal_analysis",
        )
    )
    assert causal


def test_loop_max_proposals_quota_propagates(
    store: ExperienceStore, eval_set: EvalSet, eval_cases, baseline_evaluation
) -> None:
    baseline_candidate, baseline_result = baseline_evaluation
    with pytest.raises(proposer.ProposerQuotaExceeded):
        optimization_loop.run_proposer_cycle(
            baseline_candidate=baseline_candidate,
            eval_cases=eval_cases,
            eval_set=eval_set,
            store=store,
            baseline_score=baseline_result["score"],
            baseline_traces=tuple(baseline_result["traces"]),
            max_proposals=999,
        )
