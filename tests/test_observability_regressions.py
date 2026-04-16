from spectrum_systems.modules.runtime.bottleneck_alerts import compute_bottleneck_alerts

def test_false_calm_closed() -> None:
    out=compute_bottleneck_alerts(trace_id="t", severe_drift=True, repeated_blocks=0, evidence_gap_spike=False, override_spike=False)
    assert "severe_drift" in out["outputs"]["alerts"]
