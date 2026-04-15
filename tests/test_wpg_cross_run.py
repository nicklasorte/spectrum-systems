from __future__ import annotations

from spectrum_systems.modules.wpg.policy_ops import compare_cross_run


def test_cross_run_comparison_detects_drift() -> None:
    out = compare_cross_run(run_a={"replay": {"signature": "a"}}, run_b={"replay": {"signature": "b"}}, trace_id="t1")
    assert out["outputs"]["drift_detected"] is True
    assert out["evaluation_refs"]["control_decision"]["decision"] == "WARN"
