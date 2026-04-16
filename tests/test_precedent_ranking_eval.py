from spectrum_systems.modules.runtime.precedent_ranking_eval import evaluate_precedent_ranking

def test_ranking_quality() -> None:
    out=evaluate_precedent_ranking(trace_id="t", ranked=[{"score":0.9}])
    assert out["outputs"]["decision"]=="ALLOW"
