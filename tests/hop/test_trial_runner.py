from __future__ import annotations

from spectrum_systems.modules.hop.schemas import validate_hop_artifact
from spectrum_systems.modules.hop.trial_runner import run_controlled_trial
from tests.hop.conftest import make_baseline_candidate


def test_controlled_trial_generates_report(eval_cases, eval_set, store):
    baseline = make_baseline_candidate()
    store.write_artifact(baseline)
    report = run_controlled_trial(
        baseline_candidate=baseline,
        eval_cases=eval_cases,
        eval_set=eval_set,
        store=store,
        iterations=5,
    )
    validate_hop_artifact(report, "hop_harness_trial_report")
    assert report["promotion_allowed"] is False
    assert report["best_score"] >= report["baseline_score"]
