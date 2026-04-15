from __future__ import annotations

from spectrum_systems.modules.wpg.policy_ops import evaluate_quality_slo


def test_quality_slo_freezes_when_degraded() -> None:
    out = evaluate_quality_slo(quality_score=0.5, error_budget_remaining=0.0, trace_id="t1")
    assert out["freeze_required"] is True
    assert out["evaluation_refs"]["control_decision"]["decision"] == "FREEZE"
