"""Integration tests for the BUILD-phase optimization-loop wiring.

These tests assert that:

- The sandbox + pattern-hook integration compiles and runs.
- ``run_proposer_cycle`` accepts the new ``sandbox_config``,
  ``use_sandbox``, and ``pattern_hooks`` keyword arguments.
- Pattern hooks are invoked exactly once per accepted candidate.
- Pattern hooks that raise are captured into ``hook_errors`` rather
  than crashing the cycle.
- ``use_sandbox=True`` routes the runner through the sandbox surface
  without changing the loop's existing semantics.

These tests do NOT run an optimization iteration in the
HOP-BATCH-3 sense: ``max_proposals=1`` produces a single
deterministic in-tree candidate; nothing is promoted, nothing is
certified.
"""

from __future__ import annotations

from typing import Any, Mapping

from spectrum_systems.modules.hop import (
    admission,
    baseline_harness,
    optimization_loop,
    sandbox,
)
from spectrum_systems.modules.hop.evaluator import EvalSet, evaluate_candidate
from spectrum_systems.modules.hop.experience_store import ExperienceStore
from tests.hop.conftest import make_baseline_candidate


def _runner_factory_for_baseline(_candidate: Mapping[str, Any]):
    return baseline_harness.run


def _baseline_evaluation(store: ExperienceStore, eval_set: EvalSet, eval_cases):
    candidate = make_baseline_candidate()
    ok, failures = admission.admit_candidate(candidate, eval_cases)
    assert ok, failures
    store.write_artifact(candidate)
    result = evaluate_candidate(
        candidate_payload=candidate,
        runner=baseline_harness.run,
        eval_set=eval_set,
        store=store,
    )
    return candidate, result


def test_loop_invokes_pattern_hooks_once_per_accepted_candidate(
    store: ExperienceStore, eval_set: EvalSet, eval_cases
) -> None:
    baseline_candidate, baseline_result = _baseline_evaluation(store, eval_set, eval_cases)
    invocations: list[dict[str, Any]] = []

    def _hook(*, candidate, run_bundle, store) -> None:
        invocations.append(
            {
                "candidate_id": candidate["candidate_id"],
                "score": run_bundle["score"]["score"],
            }
        )

    cycle = optimization_loop.run_proposer_cycle(
        baseline_candidate=baseline_candidate,
        eval_cases=eval_cases,
        eval_set=eval_set,
        runner_factory=_runner_factory_for_baseline,
        store=store,
        baseline_score=baseline_result["score"],
        baseline_traces=tuple(baseline_result["traces"]),
        max_proposals=1,
        pattern_hooks=[_hook],
    )
    assert len(invocations) == len(cycle.accepted_candidates)
    assert cycle.hook_errors == []


def test_loop_captures_hook_exceptions(
    store: ExperienceStore, eval_set: EvalSet, eval_cases
) -> None:
    baseline_candidate, baseline_result = _baseline_evaluation(store, eval_set, eval_cases)

    def _bad_hook(**_kwargs) -> None:
        raise RuntimeError("hook_blew_up")

    cycle = optimization_loop.run_proposer_cycle(
        baseline_candidate=baseline_candidate,
        eval_cases=eval_cases,
        eval_set=eval_set,
        runner_factory=_runner_factory_for_baseline,
        store=store,
        baseline_score=baseline_result["score"],
        baseline_traces=tuple(baseline_result["traces"]),
        max_proposals=1,
        pattern_hooks=[_bad_hook],
    )
    assert cycle.accepted_candidates  # the cycle still completed
    assert cycle.hook_errors
    assert "hook_blew_up" in cycle.hook_errors[0]["error"]


def test_loop_use_sandbox_runs_baseline_runner(
    store: ExperienceStore, eval_set: EvalSet, eval_cases
) -> None:
    """Smoke test the sandbox path. The baseline runner is importable
    so the sandbox wrapper resolves cleanly and the cycle completes.
    """
    baseline_candidate, baseline_result = _baseline_evaluation(store, eval_set, eval_cases)
    cycle = optimization_loop.run_proposer_cycle(
        baseline_candidate=baseline_candidate,
        eval_cases=eval_cases,
        eval_set=eval_set,
        runner_factory=_runner_factory_for_baseline,
        store=store,
        baseline_score=baseline_result["score"],
        baseline_traces=tuple(baseline_result["traces"]),
        max_proposals=1,
        use_sandbox=True,
        sandbox_config=sandbox.SandboxConfig(timeout_seconds=15.0),
    )
    assert cycle.accepted_candidates
    assert cycle.scores
    # The baseline runner is benign so the score is well-defined.
    assert 0.0 <= cycle.scores[0]["score"] <= 1.0


def test_loop_default_does_not_use_sandbox(
    store: ExperienceStore, eval_set: EvalSet, eval_cases
) -> None:
    """``use_sandbox`` defaults to False so existing tests stay fast."""
    baseline_candidate, baseline_result = _baseline_evaluation(store, eval_set, eval_cases)
    cycle = optimization_loop.run_proposer_cycle(
        baseline_candidate=baseline_candidate,
        eval_cases=eval_cases,
        eval_set=eval_set,
        runner_factory=_runner_factory_for_baseline,
        store=store,
        baseline_score=baseline_result["score"],
        baseline_traces=tuple(baseline_result["traces"]),
        max_proposals=1,
    )
    assert cycle.accepted_candidates
