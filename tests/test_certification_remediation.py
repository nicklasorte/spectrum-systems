from spectrum_systems.modules.governance.certification_remediation import build_certification_remediation

def test_remediation_record_emitted() -> None:
    out=build_certification_remediation(trace_id="t", certification_verdict="NEEDS_FIXES", blockers=["x"])
    assert out["outputs"]["next_actions"]
