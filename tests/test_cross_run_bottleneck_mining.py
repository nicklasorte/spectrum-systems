from spectrum_systems.modules.runtime.cross_run_bottleneck_mining import mine_cross_run_bottlenecks

def test_cross_run_outputs() -> None:
    out=mine_cross_run_bottlenecks(trace_id="t", runs=[{"reason_codes":["evidence_gap"],"cost":2.0,"promotions":1,"override_count":2,"policy_version":"1"}])
    assert out["bottleneck"]["artifact_type"]=="cross_run_bottleneck_report"
