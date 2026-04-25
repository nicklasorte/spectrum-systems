"""Optimization loop — single orchestration entrypoint for HOP-BATCH-2.

Pipeline (strict order, fail-closed at every stage):

::

    candidate_base
      -> proposer.propose_candidates           # bounded code generation
        -> mutation_policy.evaluate_proposal  # forbidden-mutation gate
          -> admission.admit_candidate        # validator + safety_checks
            -> evaluator.evaluate_candidate   # produces run/score/traces
              -> store.write_artifact         # persists everything
                -> trace_diff.compute_trace_diff
                  -> failure_analysis.build_failure_hypothesis
                    -> frontier.compute_frontier_streaming

Invariants (each enforced by tests):

- The proposer NEVER calls the evaluator or writes to the store.
- The optimization loop is the ONLY caller that orchestrates the chain.
- A candidate that fails *any* gate produces a structured failure
  artifact; the loop persists the failure and skips evaluation.
- The loop never skips the mutation policy, even if the proposer claims
  the candidate is identical to a parent.
- The loop's per-cycle quota (``max_proposals``) bounds wall-clock and
  store growth; exceeding the quota raises
  :class:`proposer.ProposerQuotaExceeded`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from spectrum_systems.modules.hop import (
    admission,
    failure_analysis,
    frontier,
    mutation_policy,
    proposer,
    trace_diff,
)
from spectrum_systems.modules.hop.evaluator import EvalSet, evaluate_candidate
from spectrum_systems.modules.hop.experience_store import (
    ExperienceStore,
    HopStoreError,
)


@dataclass
class CycleResult:
    """Outcome of a single proposer cycle (one baseline, N proposals)."""

    accepted_candidates: list[Mapping[str, Any]] = field(default_factory=list)
    rejected_proposals: list[dict[str, Any]] = field(default_factory=list)
    runs: list[Mapping[str, Any]] = field(default_factory=list)
    scores: list[Mapping[str, Any]] = field(default_factory=list)
    failures: list[Mapping[str, Any]] = field(default_factory=list)
    trace_diffs: list[Mapping[str, Any]] = field(default_factory=list)
    causal_hypotheses: list[Mapping[str, Any]] = field(default_factory=list)
    frontier_payload: Mapping[str, Any] | None = None


def _persist_failure(store: ExperienceStore, failure: Mapping[str, Any]) -> None:
    try:
        store.write_artifact(failure)
    except HopStoreError as exc:
        if "duplicate_artifact" in str(exc):
            return
        raise


def _maybe_persist_candidate(
    store: ExperienceStore, candidate: Mapping[str, Any]
) -> None:
    try:
        store.write_artifact(candidate)
    except HopStoreError as exc:
        if "duplicate_artifact" in str(exc):
            return
        raise


def _gather_traces_for_run(
    store: ExperienceStore, run_id: str
) -> list[Mapping[str, Any]]:
    traces: list[Mapping[str, Any]] = []
    for rec in store.list_traces(run_id=run_id):
        try:
            traces.append(store.read_artifact("hop_harness_trace", rec["artifact_id"]))
        except HopStoreError:
            continue
    return traces


def run_proposer_cycle(
    *,
    baseline_candidate: Mapping[str, Any],
    eval_cases: list[Mapping[str, Any]],
    eval_set: EvalSet,
    store: ExperienceStore,
    baseline_score: Mapping[str, Any] | None = None,
    baseline_traces: tuple[Mapping[str, Any], ...] | None = None,
    max_proposals: int = proposer.DEFAULT_MAX_PROPOSALS,
    max_frontier_window: int = frontier.DEFAULT_WINDOW_SIZE,
) -> CycleResult:
    """Run one proposer cycle end-to-end.

    Parameters
    ----------
    baseline_candidate
        The HOP candidate the proposer mutates from. Must be admitted +
        validated before this call (the loop does NOT re-evaluate it).
    eval_cases
        Already-validated eval-case payloads (passed to the safety scan).
    eval_set
        Immutable, manifest-verified ``EvalSet`` for the evaluator.
    store
        Live experience store. The loop is the only writer.
    baseline_score
        Optional pre-computed baseline score. If absent, no causal
        hypothesis is generated.
    baseline_traces
        Optional pre-computed baseline traces, paired with ``baseline_score``.
    max_proposals
        Per-cycle proposer quota.
    max_frontier_window
        Memory budget for the post-cycle frontier recomputation.
    """
    result = CycleResult()

    context = proposer.load_proposer_context(store)
    bundles = proposer.propose_candidates(
        baseline_candidate=baseline_candidate,
        context=context,
        max_proposals=max_proposals,
    )

    for bundle in bundles:
        candidate = bundle.candidate_payload
        proposal = bundle.mutation_proposal

        ok_policy, policy_failures = mutation_policy.evaluate_proposal(proposal)
        if not ok_policy:
            for fp in policy_failures:
                _persist_failure(store, fp)
            result.rejected_proposals.append(
                {"candidate_id": candidate["candidate_id"], "stage": "mutation_policy"}
            )
            result.failures.extend(policy_failures)
            continue

        ok_admit, admit_failures = admission.admit_candidate(candidate, eval_cases)
        if not ok_admit:
            for fp in admit_failures:
                _persist_failure(store, fp)
            result.rejected_proposals.append(
                {"candidate_id": candidate["candidate_id"], "stage": "admission"}
            )
            result.failures.extend(admit_failures)
            continue

        # Persist candidate before evaluating so the run/score artifacts
        # have a referent in the store. Idempotent on duplicates.
        _maybe_persist_candidate(store, candidate)

        run_bundle = evaluate_candidate(
            candidate_payload=candidate,
            eval_set=eval_set,
            store=store,
        )
        result.accepted_candidates.append(candidate)
        result.runs.append(run_bundle["run"])
        result.scores.append(run_bundle["score"])
        result.failures.extend(run_bundle["failures"])

        if baseline_score is not None:
            try:
                diff_payload = trace_diff.compute_trace_diff(
                    trace_diff.TraceDiffInputs(
                        baseline_score=baseline_score,
                        candidate_score=run_bundle["score"],
                        baseline_traces=baseline_traces or (),
                        candidate_traces=tuple(run_bundle["traces"]),
                    )
                )
            except trace_diff.TraceDiffError:
                continue
            try:
                store.write_artifact(diff_payload)
            except HopStoreError as exc:
                if "duplicate_artifact" not in str(exc):
                    raise
            result.trace_diffs.append(diff_payload)

            try:
                hypothesis = failure_analysis.build_failure_hypothesis(
                    failure_analysis.HypothesisInputs(
                        baseline_candidate=baseline_candidate,
                        candidate=candidate,
                        trace_diff=diff_payload,
                    )
                )
            except failure_analysis.FailureAnalysisError:
                continue
            try:
                store.write_artifact(hypothesis)
            except HopStoreError as exc:
                if "duplicate_artifact" not in str(exc):
                    raise
            result.causal_hypotheses.append(hypothesis)

    # Recompute the frontier from the live store using bounded memory.
    score_payloads = (
        store.read_artifact("hop_harness_score", rec["artifact_id"])
        for rec in store.list_scores()
    )
    frontier_payload = frontier.build_frontier_artifact(
        score_payloads,
        frontier_id=f"frontier_cycle_{baseline_candidate['candidate_id']}",
        window_size=max_frontier_window,
    )
    try:
        store.write_artifact(frontier_payload)
    except HopStoreError as exc:
        if "duplicate_artifact" not in str(exc):
            raise
    result.frontier_payload = frontier_payload
    return result
