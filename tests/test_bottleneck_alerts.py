from spectrum_systems.modules.runtime.bottleneck_alerts import compute_bottleneck_alerts

def test_alerts_for_spikes() -> None:
    out=compute_bottleneck_alerts(trace_id="t", severe_drift=True, repeated_blocks=3, evidence_gap_spike=True, override_spike=False)
    assert len(out["outputs"]["alerts"])>=2
