from spectrum_systems.modules.runtime.artifact_intelligence_reports import derive_intelligence_reports

def test_false_trust_reduced() -> None:
    out=derive_intelligence_reports(trace_id="t", indexed={"outputs":{"rows":[{"control_decision":"BLOCK"}]}})
    assert out["trust_score"] < 1.0
