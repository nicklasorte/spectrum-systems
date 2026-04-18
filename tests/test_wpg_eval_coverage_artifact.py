from spectrum_systems.modules.wpg.eval_coverage import compute_wpg_eval_coverage


def test_wpg_eval_coverage_blocking_gap() -> None:
    out = compute_wpg_eval_coverage(trace_id="t", available_eval_classes=["faq_generation"], active_stage_family="phase_b:wpg")
    assert "contradiction_detection" in out["outputs"]["missing_required_eval_classes"]
