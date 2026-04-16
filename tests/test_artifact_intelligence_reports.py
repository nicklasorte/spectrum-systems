from spectrum_systems.modules.runtime.artifact_intelligence_reports import derive_intelligence_reports

def test_reports_derived() -> None:
    out=derive_intelligence_reports(trace_id="t", indexed={"outputs":{"rows":[{"control_decision":"BLOCK"}]}})
    assert out["trust"]["snapshot_id"].startswith("TPS-")
