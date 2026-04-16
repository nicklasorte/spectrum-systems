from spectrum_systems.modules.runtime.cross_run_bottleneck_mining import mine_cross_run_bottlenecks

def test_evidence_gap_hotspots() -> None:
    out=mine_cross_run_bottlenecks(trace_id="t", runs=[{"reason_codes":["evidence_missing"],"cost":1.0,"promotions":1,"override_count":0,"policy_version":"1"}])
    assert out["evidence_gap"]["hotspots"]
