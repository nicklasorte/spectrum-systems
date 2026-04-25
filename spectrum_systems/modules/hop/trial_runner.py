"""Controlled HOP optimization trial runner (A24)."""

from __future__ import annotations

from typing import Any, Mapping

from spectrum_systems.modules.hop.artifacts import finalize_artifact, make_trace
from spectrum_systems.modules.hop.evaluator import EvalSet, evaluate_candidate
from spectrum_systems.modules.hop.experience_store import ExperienceStore
from spectrum_systems.modules.hop.optimization_loop import run_proposer_cycle
from spectrum_systems.modules.hop.schemas import validate_hop_artifact


def run_controlled_trial(
    *,
    baseline_candidate: Mapping[str, Any],
    eval_cases: list[Mapping[str, Any]],
    eval_set: EvalSet,
    store: ExperienceStore,
    iterations: int = 5,
    trace_id: str = "hop_trial_runner",
) -> dict[str, Any]:
    if iterations < 5 or iterations > 10:
        raise ValueError("hop_trial_runner_iterations_must_be_5_to_10")

    baseline_bundle = evaluate_candidate(
        candidate_payload=baseline_candidate,
        eval_set=eval_set,
        store=store,
        trace_id=trace_id,
    )
    baseline_score = baseline_bundle["score"]

    current_baseline = baseline_candidate
    frontier_scores: list[float] = [float(baseline_score["score"])]
    failure_modes: set[str] = set()
    best_score = float(baseline_score["score"])
    best_candidate_id = baseline_candidate["candidate_id"]

    for _ in range(iterations):
        cycle = run_proposer_cycle(
            baseline_candidate=current_baseline,
            eval_cases=eval_cases,
            eval_set=eval_set,
            store=store,
            baseline_score=baseline_bundle["score"],
            baseline_traces=tuple(baseline_bundle["traces"]),
            max_proposals=2,
            max_frontier_window=50,
        )
        for failure in cycle.failures:
            failure_modes.add(str(failure.get("failure_class", "unknown")))
        if cycle.scores:
            top = max(cycle.scores, key=lambda s: float(s["score"]))
            frontier_scores.append(float(top["score"]))
            if float(top["score"]) > best_score:
                best_score = float(top["score"])
                best_candidate_id = str(top["candidate_id"])
        if cycle.accepted_candidates:
            current_baseline = cycle.accepted_candidates[-1]

    report: dict[str, Any] = {
        "artifact_type": "hop_harness_trial_summary",
        "schema_ref": "hop/harness_trial_summary.schema.json",
        "schema_version": "1.0.0",
        "trace": make_trace(primary=trace_id),
        "summary_id": f"trial_{baseline_candidate['candidate_id']}_{iterations}",
        "workflow_id": "transcript_to_faq",
        "iterations": iterations,
        "baseline_candidate_id": baseline_candidate["candidate_id"],
        "baseline_score": float(baseline_score["score"]),
        "best_candidate_id": best_candidate_id,
        "best_score": best_score,
        "frontier_evolution": frontier_scores,
        "failure_modes": sorted(failure_modes),
        "advisory_only": True,
    }
    finalize_artifact(report, id_prefix="hop_trial_")
    validate_hop_artifact(report, "hop_harness_trial_summary")
    store.write_artifact(report)
    return report
