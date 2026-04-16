from spectrum_systems.modules.runtime.cross_run_bottleneck_mining import mine_cross_run_bottlenecks

def test_cross_run_not_empty() -> None:
    out=mine_cross_run_bottlenecks(trace_id="t", runs=[{"reason_codes":[],"cost":1.0,"promotions":1,"override_count":0,"policy_version":"1"}])
    assert "cost_per_promotion" in out["route"]["outputs"]
