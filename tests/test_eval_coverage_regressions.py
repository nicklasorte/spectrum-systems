from spectrum_systems.modules.wpg.eval_coverage import compute_wpg_eval_coverage

def test_mandatory_uncovered_blocks() -> None:
    out=compute_wpg_eval_coverage(trace_id="t", available_eval_classes=[], active_stage_family="phase_b:wpg")
    assert out["outputs"]["decision"]=="BLOCK"
