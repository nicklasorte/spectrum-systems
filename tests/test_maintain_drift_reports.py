from spectrum_systems.modules.runtime.maintain_drift import build_maintain_drift_reports

def test_maintain_reports() -> None:
    out=build_maintain_drift_reports(trace_id="t", stale_assumptions=1, registry_divergence=1, stale_eval_slices=0)
    assert out["maintain"]["outputs"]["severe"] is True
