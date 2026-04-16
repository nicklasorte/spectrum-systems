from spectrum_systems.modules.runtime.judgment_policy_candidates import derive_judgment_policy_candidates

def test_abuse_seam_detectable() -> None:
    out=derive_judgment_policy_candidates(trace_id="t", judgments=[{"rationale":"short"}], threshold=20)
    assert out["outputs"]["decision"]=="WARN"
