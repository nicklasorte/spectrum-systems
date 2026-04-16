from spectrum_systems.modules.runtime.judgment_policy_candidates import derive_judgment_policy_candidates

def test_candidate_count() -> None:
    out=derive_judgment_policy_candidates(trace_id="t", judgments=[{"rationale":"adequate rationale text"}])
    assert out["outputs"]["candidate_count"]==1
