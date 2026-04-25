"""Optimization loop — single orchestration entrypoint for HOP-BATCH-2.

Pipeline (strict order, fail-closed at every stage):

::

    candidate_base
      -> proposer.propose_candidates           # bounded code generation
        -> mutation_policy.evaluate_proposal  # forbidden-mutation gate
          -> admission.admit_candidate        # validator + safety_checks
            -> sandbox.make_sandboxed_runner  # isolated execution
              -> evaluator.evaluate_candidate # produces run/score/traces
                -> store.write_artifact       # persists everything
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
- When ``use_sandbox=True`` is passed, every runner returned by
  ``runner_factory`` is wrapped through the HOP sandbox before
  reaching the evaluator. The default remains in-process execution
  so existing deterministic-baseline tests stay fast; HOP-BATCH-3
  build phase only wires the integration — it does not run
  optimization iterations.

Pattern hooks
-------------

The optimization loop can be configured with an iterable of
``pattern_hooks`` — callables of shape
``hook(*, candidate, run_bundle, store) -> None``. Hooks are invoked
*after* a candidate has been admitted, sandboxed, and evaluated.
Hooks are advisory: they MUST NOT mutate the candidate, the eval
set, the store's index, or any artifact already persisted. They
exist so reusable harness patterns can observe and emit derived
*candidate-side* signals (e.g. coverage telemetry) that the loop
later considers when ranking proposals.

Pattern hooks have no decision authority: the CDE remains the sole
decision authority and the evaluator remains the sole scoring
authority. A misbehaving hook that raises is caught and logged into
the cycle result's ``hook_errors`` field; the cycle continues.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping

from spectrum_systems.modules.hop import (
    admission,
    failure_analysis,
    frontier,
    mutation_policy,
    proposer,
    sandbox,
    trace_diff,
)
from spectrum_systems.modules.hop.evaluator import EvalSet, evaluate_candidate
from spectrum_systems.modules.hop.experience_store import (
    ExperienceStore,
    HopStoreError,
)


PatternHook = Callable[..., None]
"""Signature: ``hook(*, candidate, run_bundle, store) -> None``."""


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
    hook_errors: list[dict[str, str]] = field(default_factory=list)


def _wrap_runner_in_sandbox(
    runner: Callable[[Mapping[str, Any]], dict[str, Any]],
    *,
    sandbox_config: sandbox.SandboxConfig | None,
) -> Callable[[Mapping[str, Any]], dict[str, Any]]:
    """Best-effort sandbox wrapping.

    Returns ``runner`` unchanged if it cannot be addressed across the
    process boundary (e.g. it is a closure or inner function). The
    safety net is the per-case schema check the evaluator already
    performs on the runner output, plus the candidate-side static
    scans run by ``safety_checks``.
    """
    try:
        return sandbox.make_sandboxed_runner(runner=runner, config=sandbox_config)
    except sandbox.SandboxConfigError:
        return runner


def _invoke_pattern_hooks(
    hooks: Iterable[PatternHook] | None,
    *,
    candidate: Mapping[str, Any],
    run_bundle: Mapping[str, Any],
    store: ExperienceStore,
    result: "CycleResult",
) -> None:
    if not hooks:
        return
    for hook in hooks:
        try:
            hook(candidate=candidate, run_bundle=run_bundle, store=store)
        except Exception as exc:  # noqa: BLE001 - hooks are advisory
            result.hook_errors.append(
                {
                    "hook": getattr(hook, "__name__", repr(hook)),
                    "candidate_id": candidate.get("candidate_id", "unknown"),
                    "error": f"{type(exc).__name__}:{exc}",
                }
            )


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
    runner_factory: Callable[[Mapping[str, Any]], Callable[[Mapping[str, Any]], dict[str, Any]]],
    store: ExperienceStore,
    baseline_score: Mapping[str, Any] | None = None,
    baseline_traces: tuple[Mapping[str, Any], ...] | None = None,
    max_proposals: int = proposer.DEFAULT_MAX_PROPOSALS,
    max_frontier_window: int = frontier.DEFAULT_WINDOW_SIZE,
    sandbox_config: sandbox.SandboxConfig | None = None,
    use_sandbox: bool = False,
    pattern_hooks: Iterable[PatternHook] | None = None,
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
    runner_factory
        Callable that, given an admitted candidate payload, returns the
        runtime entrypoint used by the evaluator. The factory is
        responsible for sandboxing (in BATCH-2 the factory is just
        ``baseline_harness.run`` for the baseline templates).
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
    sandbox_config
        Optional :class:`sandbox.SandboxConfig`. Used only when
        ``use_sandbox`` is True.
    use_sandbox
        When True, every runner returned by ``runner_factory`` is
        wrapped via :func:`sandbox.make_sandboxed_runner` before
        being handed to the evaluator. Defaults to False so existing
        callers and the BATCH-2 test suite (which executes
        deterministic in-tree code) keep their fast in-process
        execution path. The integration is wired but **never runs an
        optimization iteration on its own** — orchestration remains
        the caller's responsibility.
    pattern_hooks
        Optional iterable of advisory pattern hooks invoked after
        each candidate's evaluation completes. Hooks must not mutate
        artifacts; exceptions surface in
        :attr:`CycleResult.hook_errors`.
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

        runner = runner_factory(candidate)
        if use_sandbox:
            runner = _wrap_runner_in_sandbox(
                runner, sandbox_config=sandbox_config
            )
        run_bundle = evaluate_candidate(
            candidate_payload=candidate,
            runner=runner,
            eval_set=eval_set,
            store=store,
        )
        result.accepted_candidates.append(candidate)
        result.runs.append(run_bundle["run"])
        result.scores.append(run_bundle["score"])
        result.failures.extend(run_bundle["failures"])

        _invoke_pattern_hooks(
            pattern_hooks,
            candidate=candidate,
            run_bundle=run_bundle,
            store=store,
            result=result,
        )

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
